"""
General perpuses constants file

Copyright 2016-2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
nogahf@mellanox.com (Nogah Frankel)
"""

class MCAST_ROUTER_PORT:
    FIXED_OFF = 0
    LEARNING = 1
    FIXED_ON = 2

class MROUTE:
    INIT = 200
    FINISH = 201
    VIF_ADD = 202
    VIF_DEL = 203
    MFC_ADD = 204
    MFC_DEL = 205
    PIM_INIT = 208
    TABLE = 209
    MFC_ADD_PROXI = 210
    MFC_DEL_PROXI = 211
    USE_IF_INDEX = 8
    MAX_VIF = 32
    REGISET_VIF = 4
    DEFAULT_TTL = 1
    NOTIF_NOCACHE = 1
    NOTIF_WRONGVIF = 2
    NOTIF_WHOLEPKT = 3
