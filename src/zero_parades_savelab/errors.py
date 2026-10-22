class SaveLabError(Exception):
    """An actionable, user-facing refusal or validation error."""


class FormatError(SaveLabError):
    pass


class SafetyError(SaveLabError):
    pass
