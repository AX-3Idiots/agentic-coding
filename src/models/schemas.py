from pydantic import BaseModel, Field
from typing import Optional, Any
class ArchitectAgentResult(BaseModel):
    """아키텍트 에이전트 작업의 최종 결과물인 브랜치와 베이스 URL 정보를 담는 모델입니다."""

    main_branch: str = Field(
        description="모든 작업이 완료된 후의 최종 브랜치 이름입니다."
    )
class ResolverAgentResult(BaseModel):
    """코드 커밋 이후 최종 브랜치 정보를 담는 모델입니다."""

    final_url: Optional[str] = Field(
        description="최종 브랜치의 전체 URL입니다."
    )