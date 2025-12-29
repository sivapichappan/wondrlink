/**
 * PDF Processing Script
 *
 * This script reads PDFs from the old Flask app's data folder,
 * extracts text, chunks it, and uploads to Supabase.
 *
 * Run with: npx tsx scripts/process-pdfs.ts
 */

import { createClient } from '@supabase/supabase-js'
import * as fs from 'fs'
import * as path from 'path'

// Use dynamic import for pdf-parse (CommonJS module)
const pdfParse = require('pdf-parse')

// Supabase client with service role (bypasses RLS)
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)

// Path to the old Flask app's PDF data
const PDF_DATA_PATH = '/Users/sivapichappan/wonderlink-ui-attempt-2/main/data'

interface Chunk {
  text: string
  index: number
}

/**
 * Split text into chunks with overlap
 */
function chunkText(text: string, maxChars: number = 1500, overlapChars: number = 200): Chunk[] {
  const chunks: Chunk[] = []
  let start = 0
  let index = 0

  // Clean the text
  text = text.replace(/\s+/g, ' ').trim()

  while (start < text.length) {
    let end = start + maxChars

    // Try to break at a sentence boundary
    if (end < text.length) {
      const searchStart = Math.max(start + maxChars - 200, start)
      const searchText = text.slice(searchStart, end + 100)

      // Look for sentence endings
      const sentenceEnd = searchText.search(/[.!?]\s/)
      if (sentenceEnd !== -1) {
        end = searchStart + sentenceEnd + 1
      }
    }

    const chunkText = text.slice(start, end).trim()
    if (chunkText.length > 50) { // Skip very small chunks
      chunks.push({
        text: chunkText,
        index: index++
      })
    }

    // Move start with overlap
    start = end - overlapChars
    if (start >= text.length) break
  }

  return chunks
}

/**
 * Process a single PDF file
 */
async function processPDF(filePath: string): Promise<void> {
  const filename = path.basename(filePath)
  console.log(`\nProcessing: ${filename}`)

  try {
    // Read the PDF file
    const dataBuffer = fs.readFileSync(filePath)
    const pdfData = await pdfParse(dataBuffer)

    console.log(`  - Pages: ${pdfData.numpages}`)
    console.log(`  - Text length: ${pdfData.text.length} chars`)

    if (!pdfData.text || pdfData.text.length < 100) {
      console.log(`  - Skipping: Not enough text extracted`)
      return
    }

    // Check if document already exists
    const { data: existingDoc } = await supabase
      .from('pdf_documents')
      .select('id')
      .eq('filename', filename)
      .single()

    let documentId: string

    if (existingDoc) {
      console.log(`  - Document exists, updating...`)
      documentId = existingDoc.id

      // Delete existing chunks
      await supabase
        .from('pdf_chunks')
        .delete()
        .eq('document_id', documentId)
    } else {
      // Create document record
      const { data: newDoc, error: docError } = await supabase
        .from('pdf_documents')
        .insert({
          filename: filename,
          original_filename: filename,
          storage_path: `system/${filename}`,
          document_type: 'system',
          status: 'processing',
          file_size_bytes: dataBuffer.length
        })
        .select('id')
        .single()

      if (docError) {
        console.error(`  - Error creating document:`, docError)
        return
      }
      documentId = newDoc.id
    }

    // Chunk the text
    const chunks = chunkText(pdfData.text)
    console.log(`  - Chunks: ${chunks.length}`)

    // Insert chunks in batches
    const batchSize = 50
    for (let i = 0; i < chunks.length; i += batchSize) {
      const batch = chunks.slice(i, i + batchSize)
      const chunkRecords = batch.map(chunk => ({
        document_id: documentId,
        content: chunk.text,
        chunk_index: chunk.index
      }))

      const { error: chunkError } = await supabase
        .from('pdf_chunks')
        .insert(chunkRecords)

      if (chunkError) {
        console.error(`  - Error inserting chunks batch ${i}:`, chunkError)
        return
      }
    }

    // Update document status
    await supabase
      .from('pdf_documents')
      .update({
        status: 'completed',
        chunk_count: chunks.length,
        processed_at: new Date().toISOString()
      })
      .eq('id', documentId)

    console.log(`  - Success! ${chunks.length} chunks indexed`)

  } catch (error) {
    console.error(`  - Error processing ${filename}:`, error)
  }
}

/**
 * Main function
 */
async function main() {
  console.log('=================================')
  console.log('PDF Processing Script')
  console.log('=================================')
  console.log(`PDF folder: ${PDF_DATA_PATH}`)

  // Check if folder exists
  if (!fs.existsSync(PDF_DATA_PATH)) {
    console.error(`Error: PDF folder not found at ${PDF_DATA_PATH}`)
    process.exit(1)
  }

  // Find all PDF files
  const files = fs.readdirSync(PDF_DATA_PATH)
    .filter(f => f.toLowerCase().endsWith('.pdf'))

  console.log(`Found ${files.length} PDF files`)

  if (files.length === 0) {
    console.log('No PDF files to process')
    return
  }

  // Process each PDF
  for (const file of files) {
    const filePath = path.join(PDF_DATA_PATH, file)
    await processPDF(filePath)
  }

  // Summary
  const { data: docs } = await supabase
    .from('pdf_documents')
    .select('filename, status, chunk_count')
    .eq('document_type', 'system')

  console.log('\n=================================')
  console.log('Processing Complete!')
  console.log('=================================')
  console.log('\nIndexed Documents:')
  docs?.forEach(doc => {
    console.log(`  - ${doc.filename}: ${doc.chunk_count} chunks (${doc.status})`)
  })

  const { count } = await supabase
    .from('pdf_chunks')
    .select('*', { count: 'exact', head: true })

  console.log(`\nTotal chunks in database: ${count}`)
}

main().catch(console.error)
