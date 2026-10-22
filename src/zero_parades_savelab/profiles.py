"""Format parameters; these are interoperability constants, not player data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatProfile:
    id: str
    major: int
    minor: int
    changeset: str
    seed: bytes

    def matches(self, header: dict) -> bool:
        return (
            type(header.get("AppVersionMajor")) is int
            and type(header.get("AppVersionMinor")) is int
            and type(header.get("SaveRevision")) is int
            and header.get("AppVersionMajor") == self.major
            and header.get("AppVersionMinor") == self.minor
            and str(header.get("UpdatedOnChangeSet")) == self.changeset
            and header.get("SaveRevision") == 0
            and header.get("BuildTypeName") == "RELEASE"
        )


VERIFIED_PROFILE = FormatProfile(
    "release-1.1-40781", 1, 1, "40781", b"f52163935dc25a145a3eb5693a084752"
)


def editable_profile(header: dict) -> FormatProfile | None:
    return VERIFIED_PROFILE if VERIFIED_PROFILE.matches(header) else None
