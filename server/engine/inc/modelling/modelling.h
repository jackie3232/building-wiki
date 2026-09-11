#pragma once
#include "body.h"
#include "geometry.h"

class Modelling
{
public:
	// 创建基本点、线和面
	MODELLING_EXIMPORT static bool createFace(meta_impl::Body& shape, const meta_impl::Polygon2d& polygon);

	// 基本几何体
	MODELLING_EXIMPORT static bool sphere(meta_impl::Body& shape, double radius, meta_impl::Point origin = meta_impl::Point::Origin); // 球体
	// 正圆柱体 TODO

	// 简单几何体
	MODELLING_EXIMPORT static bool extrude(meta_impl::Body& shape, const meta_impl::Polygon2d& profile, double height, double elevation = 0.0);
};

