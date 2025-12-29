'use client'

import { useState, useEffect } from 'react'
import { createClient } from '@/lib/supabase/client'

interface PatientProfile {
  id: string
  patient_name: string | null
  cancer_type: string | null
  cancer_stage: string | null
  diagnosis_date: string | null
  current_treatments: Array<{ regimen?: string; status?: string }> | null
  medications: string[] | null
  symptoms: string[] | null
  biomarkers: Record<string, string> | null
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<PatientProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    try {
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return

      const { data, error } = await supabase
        .from('patient_profiles')
        .select('*')
        .eq('user_id', user.id)
        .single()

      if (error && error.code !== 'PGRST116') {
        console.error('Profile load error:', error)
      }
      setProfile(data)
    } catch {
      console.error('Failed to load profile')
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.json')) {
      setError('Please upload a JSON file')
      return
    }

    setUploading(true)
    setError('')
    setSuccess('')

    try {
      const text = await file.text()
      const profileData = JSON.parse(text)

      const { data: { user } } = await supabase.auth.getUser()
      if (!user) throw new Error('Not authenticated')

      // Extract patient information from the uploaded JSON
      const patientInfo = profileData.patient_info || profileData.patient || profileData
      const diagnosis = profileData.diagnosis || patientInfo.diagnosis || {}
      const treatments = profileData.treatments || profileData.current_treatments || []

      const profileRecord = {
        user_id: user.id,
        patient_name: patientInfo.name || patientInfo.patient_name || null,
        cancer_type: diagnosis.cancer_type || patientInfo.cancer_type || null,
        cancer_stage: diagnosis.stage || diagnosis.cancer_stage || patientInfo.cancer_stage || null,
        diagnosis_date: diagnosis.diagnosis_date || patientInfo.diagnosis_date || null,
        current_treatments: Array.isArray(treatments) ? treatments : [],
        medications: patientInfo.medications || [],
        symptoms: patientInfo.symptoms || [],
        biomarkers: diagnosis.biomarkers || patientInfo.biomarkers || {},
        raw_profile: profileData
      }

      const { error: upsertError } = await supabase
        .from('patient_profiles')
        .upsert(profileRecord, { onConflict: 'user_id' })

      if (upsertError) throw upsertError

      setSuccess('Profile uploaded successfully!')
      loadProfile()
    } catch (err) {
      console.error('Upload error:', err)
      setError('Failed to upload profile. Please check the file format.')
    } finally {
      setUploading(false)
    }
  }

  const clearProfile = async () => {
    if (!confirm('Are you sure you want to clear your patient profile?')) return

    try {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return

      await supabase
        .from('patient_profiles')
        .delete()
        .eq('user_id', user.id)

      setProfile(null)
      setSuccess('Profile cleared successfully')
    } catch {
      setError('Failed to clear profile')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Patient Profile</h1>
      <p className="text-gray-600 mb-6">
        Upload your patient profile to receive personalized guidance based on your diagnosis and treatment.
      </p>

      {/* Upload Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Profile</h2>
        <p className="text-sm text-gray-600 mb-4">
          Upload a JSON file containing your patient information. This helps WondrLink provide personalized answers.
        </p>

        <label className="block">
          <input
            type="file"
            accept=".json"
            onChange={handleFileUpload}
            disabled={uploading}
            className="block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-lg file:border-0
              file:text-sm file:font-medium
              file:bg-blue-50 file:text-blue-600
              hover:file:bg-blue-100
              disabled:opacity-50"
          />
        </label>

        {error && (
          <div className="mt-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
            {error}
          </div>
        )}
        {success && (
          <div className="mt-4 p-3 bg-green-50 text-green-600 rounded-lg text-sm">
            {success}
          </div>
        )}
      </div>

      {/* Profile Display */}
      {profile ? (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Current Profile</h2>
            <button
              onClick={clearProfile}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Clear Profile
            </button>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {profile.patient_name && (
              <div>
                <p className="text-sm text-gray-500">Patient Name</p>
                <p className="font-medium text-gray-900">{profile.patient_name}</p>
              </div>
            )}
            {profile.cancer_type && (
              <div>
                <p className="text-sm text-gray-500">Cancer Type</p>
                <p className="font-medium text-gray-900">{profile.cancer_type}</p>
              </div>
            )}
            {profile.cancer_stage && (
              <div>
                <p className="text-sm text-gray-500">Stage</p>
                <p className="font-medium text-gray-900">{profile.cancer_stage}</p>
              </div>
            )}
            {profile.diagnosis_date && (
              <div>
                <p className="text-sm text-gray-500">Diagnosis Date</p>
                <p className="font-medium text-gray-900">{profile.diagnosis_date}</p>
              </div>
            )}
          </div>

          {profile.current_treatments && profile.current_treatments.length > 0 && (
            <div className="mt-6">
              <p className="text-sm text-gray-500 mb-2">Current Treatments</p>
              <div className="flex flex-wrap gap-2">
                {profile.current_treatments.map((t, i) => (
                  <span key={i} className="px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-sm">
                    {t.regimen || JSON.stringify(t)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {profile.medications && profile.medications.length > 0 && (
            <div className="mt-6">
              <p className="text-sm text-gray-500 mb-2">Medications</p>
              <div className="flex flex-wrap gap-2">
                {profile.medications.map((med, i) => (
                  <span key={i} className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
                    {med}
                  </span>
                ))}
              </div>
            </div>
          )}

          {profile.biomarkers && Object.keys(profile.biomarkers).length > 0 && (
            <div className="mt-6">
              <p className="text-sm text-gray-500 mb-2">Biomarkers</p>
              <div className="grid gap-2 md:grid-cols-3">
                {Object.entries(profile.biomarkers).map(([key, value]) => (
                  <div key={key} className="px-3 py-2 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-500">{key}</p>
                    <p className="font-medium text-gray-900">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-gray-50 rounded-xl border border-dashed border-gray-300 p-12 text-center">
          <div className="text-4xl mb-4">📋</div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Profile Yet</h3>
          <p className="text-gray-600">
            Upload a JSON file with your patient information to get personalized guidance.
          </p>
        </div>
      )}
    </div>
  )
}
