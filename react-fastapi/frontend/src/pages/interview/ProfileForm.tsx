/**
 * pages/interview/ProfileForm.tsx
 * 事前入力フォーム（学歴・職歴・資格／免許）
 * streamlit版 interview_ui.py の render_profile_form() に相当。
 */
import React, { useState } from 'react'
import { ClipboardList, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui'

interface ProfileFormProps {
  onSubmit: (profileText: string) => void
}

function buildProfileText(education: string, workHistory: string, licenses: string): string {
  const parts: string[] = []
  if (education.trim()) parts.push(`【学歴】\n${education.trim()}`)
  if (workHistory.trim()) parts.push(`【職歴（インターン・アルバイト等）】\n${workHistory.trim()}`)
  if (licenses.trim()) parts.push(`【資格・免許】\n${licenses.trim()}`)
  return parts.join('\n\n')
}

export const ProfileForm: React.FC<ProfileFormProps> = ({ onSubmit }) => {
  const [education, setEducation] = useState('')
  const [workHistory, setWorkHistory] = useState('')
  const [licenses, setLicenses] = useState('')

  const fieldClass =
    'w-full text-sm border border-surface-200 rounded-xl px-4 py-3 resize-none ' +
    'focus:outline-none focus:ring-2 focus:ring-brand-300 text-slate-700 placeholder:text-slate-300'

  return (
    <div className="max-w-xl mx-auto px-6 py-10 animate-fade-in">
      <div className="mb-6 flex items-center gap-2">
        <ClipboardList className="w-5 h-5 text-brand-500" />
        <h1 className="text-xl font-bold text-slate-900">はじめに（事前入力・任意）</h1>
      </div>
      <p className="text-sm text-slate-500 mb-8 leading-relaxed">
        学歴・職歴・資格／免許をあらかじめ入力しておくと、インタビュー中にAIが同じ内容を
        聞き返さずに済むため、より少ない質問数でテンポよく進められます。
        （未入力のまま始めることもできます）
      </p>

      <div className="space-y-5 mb-8">
        <div>
          <label className="text-sm font-medium text-slate-700 mb-1.5 block">学歴</label>
          <textarea
            value={education}
            onChange={e => setEducation(e.target.value)}
            rows={3}
            placeholder={'例）〇〇大学 〇〇学部 〇〇学科\n2027年3月 卒業見込み'}
            className={fieldClass}
          />
        </div>
        <div>
          <label className="text-sm font-medium text-slate-700 mb-1.5 block">職歴（インターン・アルバイト等）</label>
          <textarea
            value={workHistory}
            onChange={e => setWorkHistory(e.target.value)}
            rows={3}
            placeholder={'例）〇〇株式会社にて長期インターン（2024年6月〜現在）\n△△カフェにてアルバイト（2023年4月〜2024年3月）'}
            className={fieldClass}
          />
        </div>
        <div>
          <label className="text-sm font-medium text-slate-700 mb-1.5 block">資格・免許</label>
          <textarea
            value={licenses}
            onChange={e => setLicenses(e.target.value)}
            rows={3}
            placeholder={'例）TOEIC 850点\n普通自動車第一種運転免許\n基本情報技術者試験'}
            className={fieldClass}
          />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Button
          size="lg"
          className="w-full justify-center"
          icon={<ArrowRight className="w-5 h-5" />}
          onClick={() => onSubmit(buildProfileText(education, workHistory, licenses))}
        >
          この内容でインタビューを始める
        </Button>
        <Button
          variant="ghost"
          className="w-full justify-center"
          onClick={() => onSubmit('')}
        >
          入力せずに始める
        </Button>
      </div>
    </div>
  )
}
