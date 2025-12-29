import Together from 'together-ai'

// Lazy initialization to avoid build-time errors
let togetherClient: Together | null = null

function getTogetherClient(): Together {
  if (!togetherClient) {
    togetherClient = new Together({
      apiKey: process.env.TOGETHER_API_KEY!
    })
  }
  return togetherClient
}

interface ResponseSettings {
  maxTokens: number
  systemMessage: string
}

export interface LLMResponse {
  answer: string
  apiUsed: 'together' | 'groq'
}

function getResponseSettings(responseLength: string, queryType: string): ResponseSettings {
  // Base instructions that apply to all responses
  const baseInstructions = `You are WondrLink, an expert cancer care guide powered by NCCN guidelines and clinical evidence. Your mission is to help patients understand their cancer journey with accurate, actionable information.

CORE PRINCIPLES:
1. ACCURACY FIRST: Only state facts that are supported by the provided medical sources
2. BE SPECIFIC: Include actual drug names, dosages, regimen names, percentages, and timeframes when available
3. CITE YOUR SOURCES: Reference the specific guidelines or studies when making claims
4. PATIENT-CENTERED: Explain complex concepts in accessible language, but don't oversimplify to the point of losing important details
5. ACTIONABLE: Give patients concrete information they can discuss with their healthcare team`

  // Query-type specific instructions
  const queryInstructions: Record<string, string> = {
    treatment: `
TREATMENT-SPECIFIC GUIDANCE:
- Name specific chemotherapy regimens (e.g., FOLFOX, FOLFIRI, CAPOX)
- Mention targeted therapies when relevant (e.g., bevacizumab, cetuximab)
- Explain the treatment sequence (1st line, 2nd line, etc.)
- Include information about treatment duration and cycles when available`,

    side_effect: `
SIDE EFFECT-SPECIFIC GUIDANCE:
- List specific side effects with their frequency (common, less common, rare)
- Provide practical management tips
- Mention which symptoms require immediate medical attention
- Include information about preventive medications when relevant`,

    prognosis: `
PROGNOSIS-SPECIFIC GUIDANCE:
- Provide stage-specific survival statistics when available
- Explain prognostic factors (biomarkers, tumor characteristics)
- Be honest but hopeful - emphasize that statistics are averages
- Mention factors that can improve outcomes`,

    diagnosis: `
DIAGNOSIS-SPECIFIC GUIDANCE:
- Explain what tests are used and why
- Describe what results mean in practical terms
- Mention the staging system and what each stage indicates
- Include information about biomarker testing`,

    general: `
GENERAL GUIDANCE:
- Provide comprehensive, well-organized information
- Cover the most important aspects of the topic
- Include practical next steps or questions to ask the doctor`
  }

  const querySpecificInstructions = queryInstructions[queryType] || queryInstructions.general

  const settings: Record<string, ResponseSettings> = {
    brief: {
      maxTokens: 250,
      systemMessage: `${baseInstructions}

RESPONSE FORMAT (Brief):
- Provide a concise 2-3 sentence answer
- Focus on the single most important point
- Include one specific detail or statistic
${querySpecificInstructions}

End with a brief recommendation to discuss with their healthcare team.`
    },
    normal: {
      maxTokens: 500,
      systemMessage: `${baseInstructions}

RESPONSE FORMAT (Normal):
- Provide a comprehensive 4-6 sentence answer
- Cover 2-3 key points with specific details
- Include relevant statistics, drug names, or timeframes
- Use bullet points or short paragraphs for clarity
${querySpecificInstructions}

End with a recommendation to discuss specifics with their healthcare team.`
    },
    detailed: {
      maxTokens: 800,
      systemMessage: `${baseInstructions}

RESPONSE FORMAT (Detailed):
- Provide a thorough, well-structured response
- Cover all relevant aspects of the topic
- Include specific data: drug names, dosages, percentages, durations
- Organize information with clear sections or bullet points
- Explain the reasoning behind recommendations
- Address common patient concerns or questions
${querySpecificInstructions}

Conclude with specific questions the patient might want to ask their doctor.`
    }
  }
  return settings[responseLength] || settings.normal
}

function trimIncompleteSentence(response: string): string {
  if (!response) return response
  response = response.trim()

  // If already ends with proper punctuation, return as is
  if (/[.!?"]$/.test(response)) {
    return response
  }

  // Find the last complete sentence
  const lastPunct = Math.max(
    response.lastIndexOf('.'),
    response.lastIndexOf('!'),
    response.lastIndexOf('?')
  )

  return lastPunct > 0 ? response.slice(0, lastPunct + 1) : response
}

async function callGroqFallback(
  prompt: string,
  settings: ResponseSettings,
  temperature: number
): Promise<LLMResponse> {
  const Groq = (await import('groq-sdk')).default
  const groq = new Groq({ apiKey: process.env.GROQ_API_KEY! })

  const response = await groq.chat.completions.create({
    model: 'llama-3.1-70b-versatile', // Upgraded from 8b to 70b for better quality
    messages: [
      { role: 'system', content: settings.systemMessage },
      { role: 'user', content: prompt }
    ],
    max_tokens: settings.maxTokens,
    temperature,
    top_p: 0.9
  })

  const content = response.choices[0]?.message?.content?.trim()

  if (!content) {
    throw new Error('Both Together AI and Groq failed to generate a response')
  }

  return {
    answer: trimIncompleteSentence(content),
    apiUsed: 'groq'
  }
}

export async function callLLM(
  prompt: string,
  responseLength: 'brief' | 'normal' | 'detailed' = 'normal',
  queryType: string = 'general',
  temperature: number = 0.3 // Slightly higher for more natural responses
): Promise<LLMResponse> {
  const settings = getResponseSettings(responseLength, queryType)

  try {
    const response = await getTogetherClient().chat.completions.create({
      model: 'meta-llama/Llama-3.3-70B-Instruct-Turbo',
      messages: [
        { role: 'system', content: settings.systemMessage },
        { role: 'user', content: prompt }
      ],
      max_tokens: settings.maxTokens,
      temperature,
      top_p: 0.9,
      repetition_penalty: 1.1 // Reduce repetition
    })

    const content = response.choices[0]?.message?.content?.trim()

    if (!content) {
      throw new Error('Empty response from Together AI')
    }

    return {
      answer: trimIncompleteSentence(content),
      apiUsed: 'together'
    }
  } catch (error) {
    console.warn('Together AI failed, falling back to Groq:', error)
    return callGroqFallback(prompt, settings, temperature)
  }
}
