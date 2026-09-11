#pragma once

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN             // 从 Windows 头文件中排除极少使用的内容
// Windows 头文件
#include <windows.h>
#endif
// 非 Windows 平台：无系统头，编码统一为 UTF-8（见 MyString.cpp）
