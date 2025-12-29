-- WondrLink Database Schema
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/kgcelxfhmhymutyrorpw/sql/new

-- =====================================================
-- USER PROFILES (extends Supabase Auth)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- PATIENT PROFILES
-- =====================================================
CREATE TABLE IF NOT EXISTS public.patient_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    patient_name TEXT,
    date_of_birth DATE,
    gender TEXT,
    ecog_score INTEGER CHECK (ecog_score >= 0 AND ecog_score <= 5),
    allergies TEXT[],
    comorbidities TEXT[],
    cancer_type TEXT,
    histology TEXT,
    cancer_stage TEXT,
    diagnosis_date DATE,
    disease_sites TEXT[],
    biomarkers JSONB DEFAULT '{}'::jsonb,
    current_treatments JSONB DEFAULT '[]'::jsonb,
    medications TEXT[],
    symptoms TEXT[],
    treatment_options TEXT[],
    raw_profile JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- =====================================================
-- CONVERSATIONS
-- =====================================================
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    UNIQUE(user_id, session_id)
);

-- =====================================================
-- MESSAGES
-- =====================================================
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    api_used TEXT,
    retrieved_count INTEGER DEFAULT 0,
    response_length_setting TEXT CHECK (response_length_setting IN ('brief', 'normal', 'detailed')),
    patient_context_used BOOLEAN DEFAULT false,
    validation_warnings TEXT[],
    query_type TEXT CHECK (query_type IN ('treatment', 'side_effect', 'prognosis', 'diagnosis', 'general')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sequence_number INTEGER
);

-- =====================================================
-- PDF DOCUMENTS
-- =====================================================
CREATE TABLE IF NOT EXISTS public.pdf_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN ('system', 'user_upload')),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    chunk_count INTEGER DEFAULT 0,
    file_size_bytes BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- =====================================================
-- PDF CHUNKS (for RAG search)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.pdf_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.pdf_documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    section_header TEXT,
    UNIQUE(document_id, chunk_index)
);

-- =====================================================
-- INDEXES
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON public.user_profiles(username);
CREATE INDEX IF NOT EXISTS idx_patient_profiles_user_id ON public.patient_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON public.conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_type ON public.pdf_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_pdf_chunks_document_id ON public.pdf_chunks(document_id);

-- Full-text search index for RAG
CREATE INDEX IF NOT EXISTS idx_pdf_chunks_content_gin ON public.pdf_chunks USING gin(to_tsvector('english', content));

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON public.user_profiles;
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_patient_profiles_updated_at ON public.patient_profiles;
CREATE TRIGGER update_patient_profiles_updated_at
    BEFORE UPDATE ON public.patient_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_conversations_updated_at ON public.conversations;
CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON public.conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-increment message sequence number
CREATE OR REPLACE FUNCTION set_message_sequence()
RETURNS TRIGGER AS $$
BEGIN
    SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO NEW.sequence_number
    FROM public.messages
    WHERE conversation_id = NEW.conversation_id;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS set_message_sequence_trigger ON public.messages;
CREATE TRIGGER set_message_sequence_trigger
    BEFORE INSERT ON public.messages
    FOR EACH ROW EXECUTE FUNCTION set_message_sequence();

-- Semantic search function for RAG
CREATE OR REPLACE FUNCTION search_chunks(
    query_text TEXT,
    limit_count INTEGER DEFAULT 5
)
RETURNS TABLE(
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.content,
        ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', query_text)) as rank
    FROM public.pdf_chunks c
    INNER JOIN public.pdf_documents d ON c.document_id = d.id
    WHERE
        d.status = 'completed'
        AND to_tsvector('english', c.content) @@ plainto_tsquery('english', query_text)
    ORDER BY rank DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pdf_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pdf_chunks ENABLE ROW LEVEL SECURITY;

-- User Profiles policies
DROP POLICY IF EXISTS "Users can view own profile" ON public.user_profiles;
CREATE POLICY "Users can view own profile" ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.user_profiles;
CREATE POLICY "Users can update own profile" ON public.user_profiles
    FOR UPDATE USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can insert own profile" ON public.user_profiles;
CREATE POLICY "Users can insert own profile" ON public.user_profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Patient Profiles policies
DROP POLICY IF EXISTS "Users can manage own patient profile" ON public.patient_profiles;
CREATE POLICY "Users can manage own patient profile" ON public.patient_profiles
    FOR ALL USING (auth.uid() = user_id);

-- Conversations policies
DROP POLICY IF EXISTS "Users can manage own conversations" ON public.conversations;
CREATE POLICY "Users can manage own conversations" ON public.conversations
    FOR ALL USING (auth.uid() = user_id);

-- Messages policies
DROP POLICY IF EXISTS "Users can view own messages" ON public.messages;
CREATE POLICY "Users can view own messages" ON public.messages
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create messages" ON public.messages;
CREATE POLICY "Users can create messages" ON public.messages
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- PDF Documents policies
DROP POLICY IF EXISTS "Anyone can view system documents" ON public.pdf_documents;
CREATE POLICY "Anyone can view system documents" ON public.pdf_documents
    FOR SELECT USING (document_type = 'system');

DROP POLICY IF EXISTS "Users can view own documents" ON public.pdf_documents;
CREATE POLICY "Users can view own documents" ON public.pdf_documents
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can upload documents" ON public.pdf_documents;
CREATE POLICY "Users can upload documents" ON public.pdf_documents
    FOR INSERT WITH CHECK (auth.uid() = user_id OR document_type = 'system');

-- PDF Chunks policies
DROP POLICY IF EXISTS "Chunks follow document access" ON public.pdf_chunks;
CREATE POLICY "Chunks follow document access" ON public.pdf_chunks
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.pdf_documents d
            WHERE d.id = document_id
            AND (d.document_type = 'system' OR d.user_id = auth.uid())
        )
    );

-- Allow service role to manage all data (for background jobs)
DROP POLICY IF EXISTS "Service role full access user_profiles" ON public.user_profiles;
CREATE POLICY "Service role full access user_profiles" ON public.user_profiles
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

DROP POLICY IF EXISTS "Service role full access pdf_documents" ON public.pdf_documents;
CREATE POLICY "Service role full access pdf_documents" ON public.pdf_documents
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

DROP POLICY IF EXISTS "Service role full access pdf_chunks" ON public.pdf_chunks;
CREATE POLICY "Service role full access pdf_chunks" ON public.pdf_chunks
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- =====================================================
-- STORAGE BUCKETS (run separately in Storage settings)
-- =====================================================
-- Create these buckets in Supabase Dashboard -> Storage:
-- 1. medical-pdfs (private) - for system medical documents
-- 2. user-uploads (private) - for user profile uploads
