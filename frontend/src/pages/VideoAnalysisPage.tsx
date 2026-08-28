import { UploadVideoPanel } from '@/components/cameras/UploadVideoPanel'

export function VideoAnalysisPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Video Analysis</h1>
          <p className="text-sm text-slate-500">Upload a traffic video to run the full AI analysis pipeline (YOLO → Tracking → OCR → Speed → Violations).</p>
        </div>
      </div>

      <section>
        <UploadVideoPanel />
      </section>
    </div>
  )
}

export default VideoAnalysisPage
