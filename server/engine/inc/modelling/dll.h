#pragma once

#define DISALLOW_COPY(TypeName)            \
    TypeName(const TypeName&) = delete;    \
    TypeName& operator=(const TypeName&) = delete;

#if defined(_WIN32)
#  ifdef MODELLING_MODULE
#    define MODELLING_EXIMPORT __declspec(dllexport)
#  else
#    define MODELLING_EXIMPORT __declspec(dllimport)
#  endif
#else
// 非 Windows：modelling 以静态库直接编入可执行，无导入/导出语义
#  define MODELLING_EXIMPORT
#endif
