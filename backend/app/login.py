"""Interactive one-time Apple Account login for FindMy.py."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from findmy import (
    AppleAccount,
    LocalAnisetteProvider,
    LoginState,
    SmsSecondFactorMethod,
    TrustedDeviceSecondFactorMethod,
)


def login(output: Path, anisette_path: Path) -> None:
    """Perform interactive login and save the reusable session with private permissions."""

    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    anisette_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.umask(0o077)

    account = AppleAccount(LocalAnisetteProvider(libs_path=str(anisette_path)))
    email = input("Apple Account email: ").strip()
    password = getpass.getpass("Apple Account password: ")
    state = account.login(email, password)

    if state == LoginState.REQUIRE_2FA:
        methods = account.get_2fa_methods()
        for index, method in enumerate(methods):
            if isinstance(method, TrustedDeviceSecondFactorMethod):
                label = "Trusted device"
            elif isinstance(method, SmsSecondFactorMethod):
                label = f"SMS ({method.phone_number})"
            else:
                label = type(method).__name__
            print(f"{index}: {label}")

        selected = int(input("2FA method number: "))
        method = methods[selected]
        method.request()
        method.submit(input("2FA code: ").strip())

    account.to_json(output)
    output.chmod(0o600)
    account.close()
    print(f"Saved reusable Apple session to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("secrets/account.json"))
    parser.add_argument("--anisette", type=Path, default=Path("secrets/ani_libs.bin"))
    args = parser.parse_args()
    login(args.output, args.anisette)


if __name__ == "__main__":
    main()
