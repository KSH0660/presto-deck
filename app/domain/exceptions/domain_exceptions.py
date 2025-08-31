"""도메인 예외 정의"""


class DomainException(Exception):
    """도메인 레벨 기본 예외"""

    pass


class DeckNotFoundError(DomainException):
    """덱을 찾을 수 없음"""

    pass


class SlideNotFoundError(DomainException):
    """슬라이드를 찾을 수 없음"""

    pass


class InvalidSlideContentError(DomainException):
    """잘못된 슬라이드 콘텐츠"""

    pass


class TemplateNotFoundError(DomainException):
    """템플릿을 찾을 수 없음"""

    pass


class RenderingFailedError(DomainException):
    """렌더링 실패"""

    pass


class PlanningFailedError(DomainException):
    """계획 수립 실패"""

    pass
