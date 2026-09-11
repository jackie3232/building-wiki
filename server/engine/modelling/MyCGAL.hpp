#pragma once

#ifdef Handle
#define REDEFINE_HANDLE
#undef Handle
#endif

#include <CGAL/number_type_config.h>
#include <CGAL/Simple_cartesian.h>
#include <CGAL/Arr_segment_traits_2.h>
#include <CGAL/Arrangement_2.h>
#include <CGAL/Polygon_2.h>
#include <CGAL/Polygon_with_holes_2.h>
#include <CGAL/Arr_circle_segment_traits_2.h>
#include <boost/variant.hpp>
#include <CGAL/Arr_curve_data_traits_2.h>
#include <CGAL/Gps_circle_segment_traits_2.h>
#include <CGAL/Aff_transformation_2.h>

typedef CGAL::Simple_cartesian<double> Kernel;
typedef Kernel::Point_2 Point_2;
typedef Kernel::Vector_2 Vector_2;
typedef Kernel::Direction_2 Direction_2;
typedef Kernel::Circle_2 Circle_2;
typedef Kernel::Line_2 Line_2;
typedef Kernel::Segment_2 Segment_2;
typedef CGAL::Polygon_2<Kernel> Polygon_2;
typedef CGAL::Polygon_with_holes_2<Kernel> Polygon_with_holes_2;
typedef CGAL::Aff_transformation_2<Kernel> Transformation_2;

// Arrangement 中线段的 traits 和类型定义
typedef CGAL::Arr_segment_traits_2<Kernel> Arr_Segment_traits_2;
typedef Arr_Segment_traits_2::X_monotone_curve_2 Arr_Segment_2;

// 定义 Arrangement 类型
typedef CGAL::Arrangement_2<Arr_Segment_traits_2> Arrangement_2;
typedef CGAL::Arr_walk_along_line_point_location<Arrangement_2> Arr_Pointlocation;
typedef Arrangement_2::Vertex_handle Arr_Vertex_handle;
typedef Arrangement_2::Vertex_const_handle Arr_Vertex_const_handle;
typedef Arrangement_2::Halfedge Arr_Halfedge;
typedef Arrangement_2::Halfedge_handle Arr_Halfedge_handle;
typedef Arrangement_2::Halfedge_const_handle Arr_Halfedge_const_handle;
typedef Arrangement_2::Face Arr_Face;
typedef Arrangement_2::Face_handle Arr_Face_handle;
typedef Arrangement_2::Face_const_handle Arr_Face_const_handle;
typedef Arrangement_2::Vertex_iterator Arr_Vertex_iterator;
typedef Arrangement_2::Halfedge_iterator Arr_Halfedge_iterator;
typedef Arrangement_2::Edge_iterator Arr_Edge_iterator;
typedef Arrangement_2::Face_iterator Arr_Face_iterator;
typedef Arrangement_2::Halfedge_around_vertex_circulator Arr_Halfedge_around_vertex_circulator;
typedef boost::variant<Arr_Vertex_const_handle, Arr_Halfedge_const_handle, Arr_Face_const_handle> Arr_topology_item;


#ifdef REDEFINE_HANDLE
#define Handle opencascade::Handle
#undef REDEFINE_HANDLE
#endif
