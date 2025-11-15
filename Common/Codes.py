# -*- coding: utf-8 -*-
"""
Модуль кодов выхода

"""

from enum import IntEnum

#----------------------------------------------------------------
class ExitCode(IntEnum): 
    Ok = 0,
    AsyncStartError = 1,
    ControlParametersError = 2,
    InputParametersError = 3