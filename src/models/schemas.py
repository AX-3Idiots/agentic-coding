from pydantic import BaseModel, Field
from typing import Optional
class ArchitectAgentResult(BaseModel):
    """아키텍트 에이전트 작업의 최종 결과물인 브랜치와 베이스 URL 정보를 담는 모델입니다."""

    main_branch: str = Field(
        description="모든 작업이 완료된 후의 최종 브랜치 이름입니다."
    )
    base_url: str = Field(
        description="해당 브랜치의 기준이 되는 원격 저장소의 기본 URL입니다."
    )
    branch_url: str = Field(
        description="해당 브랜치의 전체 URL입니다."
    )
    project_dir: str = Field(
        description="생성된 프로젝트 폴더 경로입니다."
    )
class ResolverAgentResult(BaseModel):
    """코드 충돌 해결 에이전트 작업의 최종 결과물인 코드 블럭을 담는 모델입니다."""

    final_code: Optional[str] = Field(
        description="충돌이 해결된 코드 블럭입니다."
    )