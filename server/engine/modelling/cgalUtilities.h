#pragma once
#include "MyCGAL.hpp"
#include "geometry.h"

class cgalUtilities
{
public:
	static meta_impl::LineSegment2d convert(const Arr_Segment_2& segment);
	static void convert(const meta_impl::Polygon2d& from, Polygon_2& to);
	static void convert(const Polygon_with_holes_2& from, meta_impl::Polygon2d& to); // 不考虑孔洞

	static Point_2 middle_point_of(const Arr_Segment_2& segment);
	static double length(const Arr_Segment_2& segment);

	// 判断在阈值范围内是否在线上
	static bool is_on_edge(Arr_Halfedge_handle& he, Arr_Face_handle face, const Point_2& pnt, const meta_impl::MyTol& tol = meta_impl::MyTol::dTol);

	static bool get_outer_loop_of(const std::set<Arr_Face_handle>& faces, const Arrangement_2& arrangement, std::vector<Arr_Halfedge_handle>& halfedges);

	static std::string from(const Point_2& pnt);
};

