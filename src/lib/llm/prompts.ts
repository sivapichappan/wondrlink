export interface PatientContext {
  cancerType?: string
  cancerStage?: string
  currentTreatments?: string[]
  medications?: string[]
  symptoms?: string[]
  biomarkers?: Record<string, string>
  diagnosisDate?: string
  age?: number
  gender?: string
}

export function classifyQueryType(query: string): string {
  const queryLower = query.toLowerCase()

  // More comprehensive keyword matching
  const treatmentPatterns = [
    'treatment', 'therapy', 'drug', 'medication', 'chemo', 'chemotherapy',
    'radiation', 'surgery', 'regimen', 'folfox', 'folfiri', 'capox',
    'bevacizumab', 'cetuximab', 'immunotherapy', 'targeted therapy',
    'first line', 'second line', '1st line', '2nd line', 'adjuvant',
    'neoadjuvant', 'maintenance', 'what drugs', 'which treatment'
  ]
  const sideEffectPatterns = [
    'side effect', 'adverse', 'symptom', 'nausea', 'fatigue', 'tired',
    'pain', 'hair loss', 'diarrhea', 'vomiting', 'neuropathy', 'numbness',
    'tingling', 'cold sensitivity', 'mouth sores', 'appetite', 'weight',
    'infection', 'fever', 'blood count', 'neutropenia', 'manage', 'cope',
    'deal with', 'help with'
  ]
  const prognosisPatterns = [
    'prognosis', 'survival', 'outcome', 'chance', 'cure', 'remission',
    'recurrence', 'come back', 'spread', 'metastasis', 'metastatic',
    'life expectancy', 'how long', 'statistics', 'odds', 'likelihood'
  ]
  const diagnosisPatterns = [
    'diagnos', 'test', 'scan', 'ct', 'mri', 'pet', 'colonoscopy',
    'biopsy', 'marker', 'genetic', 'mutation', 'kras', 'braf', 'msi',
    'cea', 'stage', 'staging', 'what does', 'mean', 'results'
  ]
  const screeningPatterns = [
    'screen', 'prevention', 'prevent', 'risk', 'family history',
    'hereditary', 'lynch', 'when should', 'how often', 'check'
  ]

  // Check patterns with priority
  if (treatmentPatterns.some(kw => queryLower.includes(kw))) return 'treatment'
  if (sideEffectPatterns.some(kw => queryLower.includes(kw))) return 'side_effect'
  if (prognosisPatterns.some(kw => queryLower.includes(kw))) return 'prognosis'
  if (diagnosisPatterns.some(kw => queryLower.includes(kw))) return 'diagnosis'
  if (screeningPatterns.some(kw => queryLower.includes(kw))) return 'screening'

  return 'general'
}

export function formatPatientContext(profile: PatientContext): string {
  const parts: string[] = []

  if (profile.cancerType) {
    parts.push(`• Cancer Type: ${profile.cancerType}`)
  }
  if (profile.cancerStage) {
    parts.push(`• Stage: ${profile.cancerStage}`)
  }
  if (profile.diagnosisDate) {
    parts.push(`• Diagnosis Date: ${profile.diagnosisDate}`)
  }
  if (profile.age) {
    parts.push(`• Age: ${profile.age}`)
  }
  if (profile.gender) {
    parts.push(`• Gender: ${profile.gender}`)
  }
  if (profile.currentTreatments && profile.currentTreatments.length > 0) {
    parts.push(`• Current Treatments: ${profile.currentTreatments.join(', ')}`)
  }
  if (profile.medications && profile.medications.length > 0) {
    parts.push(`• Medications: ${profile.medications.join(', ')}`)
  }
  if (profile.symptoms && profile.symptoms.length > 0) {
    parts.push(`• Current Symptoms: ${profile.symptoms.join(', ')}`)
  }
  if (profile.biomarkers && Object.keys(profile.biomarkers).length > 0) {
    const biomarkerStr = Object.entries(profile.biomarkers)
      .map(([key, value]) => `${key}: ${value}`)
      .join(', ')
    parts.push(`• Biomarkers: ${biomarkerStr}`)
  }

  return parts.length > 0 ? parts.join('\n') : ''
}

export function expandQuery(query: string, queryType: string): string {
  // Add related terms to improve search
  const expansions: Record<string, string[]> = {
    treatment: ['chemotherapy', 'regimen', 'therapy', 'drug', 'protocol'],
    side_effect: ['adverse effects', 'toxicity', 'management', 'symptoms'],
    prognosis: ['survival', 'outcome', 'stage', 'recurrence'],
    diagnosis: ['staging', 'workup', 'testing', 'biomarker'],
    screening: ['prevention', 'colonoscopy', 'early detection']
  }

  const additionalTerms = expansions[queryType] || []
  // Return original query - expansion happens via the search
  return query
}

export function assemblePrompt(
  userMessage: string,
  retrievedChunks: string[],
  patientContext: PatientContext | null,
  conversationHistory: string,
  queryType: string
): string {
  const parts: string[] = []

  // Start with clear context header
  parts.push('=== CONTEXT FOR ANSWERING ===')

  // Add patient context prominently if available
  if (patientContext && Object.keys(patientContext).length > 0) {
    const formattedContext = formatPatientContext(patientContext)
    if (formattedContext) {
      parts.push(`
📋 PATIENT PROFILE:
${formattedContext}

IMPORTANT: Tailor your response to this specific patient's situation, stage, and current treatments.`)
    }
  }

  // Add retrieved medical information with clear labeling
  if (retrievedChunks.length > 0) {
    parts.push(`
📚 MEDICAL REFERENCE INFORMATION (from NCCN Guidelines and Clinical Sources):
${retrievedChunks.map((chunk, i) => `
--- Source ${i + 1} ---
${chunk.trim()}
`).join('\n')}

IMPORTANT: Base your answer on the above medical sources. Cite specific information when available.`)
  } else {
    parts.push(`
⚠️ NOTE: No directly relevant medical sources were found for this query.
Provide general guidance based on established cancer care principles, and clearly indicate when you're speaking generally vs. from specific sources.`)
  }

  // Add conversation context for continuity
  if (conversationHistory && conversationHistory.trim()) {
    parts.push(`
💬 RECENT CONVERSATION:
${conversationHistory}

Use this context to provide a coherent, connected response.`)
  }

  // Add the question with emphasis
  parts.push(`
=== PATIENT'S QUESTION ===
"${userMessage}"

Query Type Detected: ${queryType.toUpperCase()}`)

  // Add specific instructions based on query type
  const queryInstructions: Record<string, string> = {
    treatment: `
Focus on: Specific treatment regimens, drug names, treatment sequences, duration of therapy, and what to expect during treatment.`,
    side_effect: `
Focus on: Common and serious side effects, practical management strategies, when to call the doctor, and preventive measures.`,
    prognosis: `
Focus on: Stage-specific information, prognostic factors, survival statistics (with appropriate context), and factors that influence outcomes.`,
    diagnosis: `
Focus on: Explaining test results, staging criteria, what different findings mean, and next steps in the diagnostic workup.`,
    screening: `
Focus on: Screening recommendations by age and risk level, screening test options, and prevention strategies.`,
    general: `
Focus on: Providing comprehensive, accurate information that addresses the patient's underlying concern.`
  }

  parts.push(`
=== RESPONSE GUIDELINES ===
${queryInstructions[queryType] || queryInstructions.general}

Remember to:
1. Be specific - include actual names, numbers, and timeframes
2. Be accurate - only state what's supported by the sources
3. Be helpful - give actionable information
4. Be caring - acknowledge the patient's situation with empathy`)

  return parts.join('\n')
}

export function detectUrgency(message: string): boolean {
  const urgencyKeywords = [
    'emergency', 'urgent', 'severe pain', 'can\'t breathe', 'bleeding heavily',
    'fever over 101', 'fever over 38', 'high fever', 'chest pain', 'fainting',
    'unconscious', 'seizure', 'allergic reaction', 'swelling throat',
    'difficulty breathing', 'blood in stool', 'can\'t keep anything down',
    'severe diarrhea', 'confusion', 'sudden weakness', 'stroke'
  ]

  const messageLower = message.toLowerCase()
  return urgencyKeywords.some(kw => messageLower.includes(kw))
}

export function addMedicalDisclaimer(response: string, isUrgent: boolean): string {
  if (isUrgent) {
    return `⚠️ **URGENT - SEEK IMMEDIATE CARE**

The symptoms you're describing may require immediate medical attention. Please:
1. Contact your oncology team's emergency line immediately
2. If you can't reach them, go to the emergency room
3. Don't wait to see if symptoms improve

---

${response}`
  }
  return response
}
