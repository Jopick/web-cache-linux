# -*- coding: utf-8 -*-
"""
Точка входа

"""

import sys,asyncio
from Common.Codes import ExitCode
from Interfaces.Main import Interface
from typing import NoReturn

#--------------------------------------------------------------------------------
class ExitStatus():
    def __init__(self):
        self.status:int = ExitCode.Ok.value

#--------------------------------------------------------------------------------
def main() -> NoReturn:
    exitStatus:ExitStatus = ExitStatus()
    loop:'asyncio.windows_events.ProactorEventLoop' = asyncio.get_event_loop()
    appEntryPoint:Interface = Interface()
    # Обеспечиваем асинхронный цикл работы
    try:
        loop.run_until_complete(appEntryPoint.Run(exitStatus)) 
        sys.exit(exitStatus.status)
    except asyncio.exceptions.CancelledError:
        sys.exit(ExitCode.AsyncStartError.value)

if __name__ == '__main__': 
    main()               