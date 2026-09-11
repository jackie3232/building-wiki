#include "pch.h"
#include "occUtilities.h"
#include "gp_Trsf.hxx"
#include "geometry.h"
#include "gp_Ax3.hxx"

using namespace meta_impl;
gp_Trsf occUtilities::from(const Matrix3d& mat)
{
	// 提取原点和轴的方向  
	gp_Pnt origin(mat.origin.x, mat.origin.y, mat.origin.z);
	gp_Dir xDirection(mat.xaxis.x, mat.xaxis.y, mat.xaxis.z);
	gp_Dir yDirection(mat.yaxis.x, mat.yaxis.y, mat.yaxis.z);
	gp_Dir zDirection(mat.zaxis.x, mat.zaxis.y, mat.zaxis.z);

	// 创建从坐标系 (fromSystem)  
	gp_Ax3 fromSystem(origin, zDirection, xDirection); // 从 Matrix3d 定义的坐标系  

	// 创建到世界坐标系 (toSystem)  
	gp_Pnt wcsOrigin(0.0, 0.0, 0.0); // WCS 原点  
	gp_Dir wcsX(1.0, 0.0, 0.0); // WCS X 方向  
	gp_Dir wcsY(0.0, 1.0, 0.0); // WCS Y 方向  
	gp_Dir wcsZ(0.0, 0.0, 1.0); // WCS Z 方向  
	gp_Ax3 toSystem(wcsOrigin, wcsZ, wcsX); // WCS 坐标系  

	// 创建 gp_Trsf 对象  
	gp_Trsf transformation;
	transformation.SetTransformation(fromSystem, toSystem);

	return transformation;
}
