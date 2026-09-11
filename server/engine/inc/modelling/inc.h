#pragma once

#if defined(_MSC_VER) && !defined(MODELLING_MODULE)
#pragma comment(lib,"modelling.lib")   // 仅 MSVC 的自动链接指令
#endif

#include "dll.h"
#include "mystring.h"
#include "RandomColor.h"
#include "geometry.h"
#include "modelling.h"
#include "site.h"
#include "topology.h"
#include "LayoutNet.h"