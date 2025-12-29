import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { assemblePrompt, classifyQueryType, detectUrgency, addMedicalDisclaimer, PatientContext } from '@/lib/llm/prompts'

// Enhanced search that combines multiple search strategies
async function searchRelevantChunks(
  supabase: Awaited<ReturnType<typeof createClient>>,
  query: string,
  queryType: string,
  limit: number = 8
): Promise<string[]> {
  const results: Map<string, { content: string; rank: number }> = new Map()

  // Strategy 1: Direct full-text search
  const { data: directResults } = await supabase
    .rpc('search_chunks', { query_text: query, limit_count: limit })

  directResults?.forEach((chunk: { content: string; rank: number; chunk_id: string }) => {
    results.set(chunk.chunk_id, { content: chunk.content, rank: chunk.rank * 1.5 }) // Boost direct matches
  })

  // Strategy 2: Search with query type keywords
  const queryTypeKeywords: Record<string, string> = {
    treatment: 'chemotherapy regimen FOLFOX FOLFIRI treatment protocol',
    side_effect: 'adverse effects toxicity side effects management symptoms',
    prognosis: 'survival outcome prognosis stage recurrence',
    diagnosis: 'staging diagnosis biomarker testing CEA',
    screening: 'screening colonoscopy prevention early detection'
  }

  const additionalSearch = queryTypeKeywords[queryType]
  if (additionalSearch) {
    const { data: typeResults } = await supabase
      .rpc('search_chunks', { query_text: `${query} ${additionalSearch}`, limit_count: limit })

    typeResults?.forEach((chunk: { content: string; rank: number; chunk_id: string }) => {
      if (!results.has(chunk.chunk_id)) {
        results.set(chunk.chunk_id, { content: chunk.content, rank: chunk.rank })
      }
    })
  }

  // Sort by rank and return top results
  const sortedResults = Array.from(results.entries())
    .sort((a, b) => b[1].rank - a[1].rank)
    .slice(0, limit)
    .map(([, value]) => value.content)

  return sortedResults
}

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient()

    // Verify authentication
    const { data: { user }, error: authError } = await supabase.auth.getUser()
    if (authError || !user) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 })
    }

    const body = await request.json()
    const { message, response_length = 'normal', session_id = 'default' } = body

    if (!message) {
      return NextResponse.json({ error: 'No message provided' }, { status: 400 })
    }

    // Classify query type early for better search
    const queryType = classifyQueryType(message)

    // Get or create conversation
    let { data: conversation } = await supabase
      .from('conversations')
      .select('id')
      .eq('user_id', user.id)
      .eq('session_id', session_id)
      .single()

    if (!conversation) {
      const { data: newConversation, error: convError } = await supabase
        .from('conversations')
        .insert({
          user_id: user.id,
          session_id,
          title: message.slice(0, 50)
        })
        .select('id')
        .single()

      if (convError) {
        console.error('Conversation creation error:', convError)
        return NextResponse.json({ error: 'Failed to create conversation' }, { status: 500 })
      }
      conversation = newConversation
    }

    // Get patient profile with more fields
    const { data: patientProfile } = await supabase
      .from('patient_profiles')
      .select('*')
      .eq('user_id', user.id)
      .single()

    const patientContext: PatientContext | null = patientProfile ? {
      cancerType: patientProfile.cancer_type,
      cancerStage: patientProfile.cancer_stage,
      diagnosisDate: patientProfile.diagnosis_date,
      currentTreatments: patientProfile.current_treatments?.map((t: { regimen?: string }) => t.regimen).filter(Boolean) || [],
      medications: patientProfile.medications || [],
      symptoms: patientProfile.symptoms || [],
      biomarkers: patientProfile.biomarkers || {}
    } : null

    // Get conversation history (last 6 exchanges = 12 messages)
    const { data: history } = await supabase
      .from('messages')
      .select('role, content')
      .eq('conversation_id', conversation.id)
      .order('sequence_number', { ascending: false })
      .limit(12)

    const conversationHistory = history?.reverse()
      .map((m, i) => `${m.role === 'user' ? 'Q' : 'A'}${Math.floor(i/2) + 1}: ${m.content}`)
      .join('\n') || ''

    // Enhanced search for relevant chunks (more chunks for better context)
    const retrievedTexts = await searchRelevantChunks(
      supabase,
      message,
      queryType,
      response_length === 'detailed' ? 10 : 8 // More chunks for detailed responses
    )

    // Check for urgency
    const isUrgent = detectUrgency(message)

    // Assemble prompt with query type
    const prompt = assemblePrompt(
      message,
      retrievedTexts,
      patientContext,
      conversationHistory,
      queryType
    )

    // Call LLM with query type for specialized responses (dynamic import to avoid build-time errors)
    const { callLLM } = await import('@/lib/llm/together')
    const { answer, apiUsed } = await callLLM(
      prompt,
      response_length as 'brief' | 'normal' | 'detailed',
      queryType
    )

    // Add medical disclaimer if needed
    const finalAnswer = addMedicalDisclaimer(answer, isUrgent)

    // Store messages
    const messagesToInsert = [
      {
        conversation_id: conversation.id,
        user_id: user.id,
        role: 'user',
        content: message,
        query_type: queryType,
        response_length_setting: response_length
      },
      {
        conversation_id: conversation.id,
        user_id: user.id,
        role: 'assistant',
        content: finalAnswer,
        api_used: apiUsed,
        retrieved_count: retrievedTexts.length,
        patient_context_used: !!patientProfile
      }
    ]

    await supabase.from('messages').insert(messagesToInsert)

    return NextResponse.json({
      answer: finalAnswer,
      api_used: apiUsed,
      retrieved_count: retrievedTexts.length,
      patient_context_used: !!patientProfile,
      query_type: queryType,
      is_urgent: isUrgent
    })

  } catch (error) {
    console.error('Chat API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
