import { DamageAssessmentUpload } from "@/components/damage-assessment";
import { PageHead } from "@/components/ui/primitives";

export default function VisionPage() {
  return <>
    <PageHead eyebrow="Real Vision Inspection" title="사진 기반 손상 등급 판독" sub="Gemini Vision이 이미지의 외관 손상을 S·A·B·C 네 단계로 분류합니다. 최종 판정은 허브 실물 검수로 확정합니다." />
    <DamageAssessmentUpload />
  </>;
}
