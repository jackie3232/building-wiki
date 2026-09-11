#include "pch.h"
#include "cgalUtilities.h"

using namespace meta_impl;
LineSegment2d cgalUtilities::convert(const Arr_Segment_2& segment)
{
	return LineSegment2d(Point2d(segment.source().x(), segment.source().y()), Point2d(segment.target().x(), segment.target().y()));
}

void cgalUtilities::convert(const Polygon2d& from, Polygon_2& to)
{
	// 清空目标多边形
	to.clear();

	// 遍历 Polygon2d 中的点，将其转换为 CGAL 的 Point_2
	for (int i = 0; i < from.pointSize(); ++i)
	{
		Point2d pnt = from.point(i);
		Point_2 cgal_point(pnt.x, pnt.y);

		// 将点添加到 CGAL Polygon_2 中
		to.push_back(cgal_point);
	}
}

void cgalUtilities::convert(const Polygon_with_holes_2& from, Polygon2d& to)
{
	to.clear();  // 清除 Polygon2d 对象中已有的点和弧信息

	// 获取多边形的外边界
	const Polygon_2& outer_boundary = from.outer_boundary();

	// 将外边界的点添加到 Polygon2d 中
	for (auto it = outer_boundary.vertices_begin(); it != outer_boundary.vertices_end(); ++it) 
	{
		const Point_2& p = *it;
		to.push_back(Point2d(p.x(), p.y()));
	}
}

Point_2 cgalUtilities::middle_point_of(const Arr_Segment_2& segment)
{
	return CGAL::midpoint(segment.source(), segment.target());
}

double cgalUtilities::length(const Arr_Segment_2& segment)
{
	Point_2 p1 = segment.source();
	Point_2 p2 = segment.target();
	return CGAL::sqrt(CGAL::to_double((p1.x() - p2.x()) * (p1.x() - p2.x()) +
		(p1.y() - p2.y()) * (p1.y() - p2.y())));
}

bool cgalUtilities::is_on_edge(Arr_Halfedge_handle& he, Arr_Face_handle face, const Point_2& pnt, const MyTol& tol)
{
	Arrangement_2::Ccb_halfedge_circulator it;
	if (face->is_unbounded())
		it = *face->inner_ccbs_begin(); // 获取第一个内边框
	else
		it = face->outer_ccb();

	Arrangement_2::Ccb_halfedge_circulator it_first = it;
	Point2d pnt_(pnt.x(), pnt.y());
	do
	{
		Arr_Halfedge_handle he1 = it;

		LineSegment2d lineSegment = cgalUtilities::convert(he1->curve());
		double distance = lineSegment.distanceTo(pnt_);
		if (distance > 0 && distance <= tol.equalPoint())
		{
			he = he1;
			return true;
		}

	} while (++it != it_first);

	return false;
}

bool cgalUtilities::get_outer_loop_of(const std::set<Arr_Face_handle>& faces,
	const Arrangement_2& arrangement, std::vector<Arr_Halfedge_handle>& halfedges)
{
	// 清空输出向量
	halfedges.clear();

	// 找到一个非共享的 halfedge 作为起点
	Arr_Halfedge_handle startHalfedge;

	for (const auto& face : faces) {
		// 检查面是否有效
		if (face->is_unbounded()) {
			continue; // 跳过无效面或无界面
		}

		// 获取面的外环
		Arr_Halfedge_handle outer_ccb = face->outer_ccb();
		Arr_Halfedge_handle curr = outer_ccb;

		// 遍历外环的所有半边
		do {
			// 检查当前 halfedge 是否是非共享的
			if (faces.find(curr->twin()->face()) == faces.end()) {
				startHalfedge = curr; // 找到起点
				break;
			}
			curr = curr->next();
		} while (curr != outer_ccb); // 回到起点时结束循环

		if (startHalfedge.ptr()) {
			break; // 找到起点后退出循环
		}
	}

	// 如果没有找到起点，返回 false
	if (startHalfedge.ptr() == nullptr) {
		return false;
	}

	// 从起点开始构建环
	Arr_Halfedge_handle currentHalfedge = startHalfedge;
	halfedges.push_back(currentHalfedge);

	// 记录上一个 halfedge，避免回到上一个 halfedge
	Arr_Halfedge_handle previousHalfedge = currentHalfedge;

	// 设置最大循环次数，防止死循环
	const int maxIterations = 10000; // 根据实际情况调整
	int iterationCount = 0;

	// 遍历直到回到起点
	while (true) {
		// 检查循环次数是否超过最大值
		if (++iterationCount > maxIterations) {
			halfedges.clear();
			return false; // 超过最大循环次数，返回 false
		}

		// 获取当前 halfedge 的终点
		Arr_Vertex_handle currentVertex = currentHalfedge->target();

		// 遍历当前顶点的所有入边
		Arr_Halfedge_around_vertex_circulator circ = currentVertex->incident_halfedges();
		Arr_Halfedge_around_vertex_circulator start = circ;

		bool foundNext = false;
		do {
			// 获取当前 halfedge 的反向边
			Arr_Halfedge_handle twin = circ->twin();

			// 检查反向边是否是从当前顶点出发的出边
			if (twin->source() == currentVertex) {
				// 检查当前 halfedge 是否是最外侧边界
				if (faces.find(twin->face()) != faces.end() &&
					faces.find(twin->twin()->face()) == faces.end()) {
					// 确保不是回到上一个 halfedge
					if (twin != previousHalfedge->twin()) {
						// 找到下一个 halfedge
						previousHalfedge = currentHalfedge;
						currentHalfedge = twin;
						halfedges.push_back(currentHalfedge);
						foundNext = true;
						break;
					}
				}
			}
		} while (++circ != start);

		// 如果没有找到下一个 halfedge，返回 false
		if (!foundNext) {
			halfedges.clear();
			return false;
		}

		// 如果回到起点，结束循环
		if (currentHalfedge->target() == startHalfedge->source()) {
			break;
		}
	}

	// 如果成功提取了最外侧的 halfedges，返回 true
	return !halfedges.empty();
}

std::string cgalUtilities::from(const Point_2& pnt)
{
	std::ostringstream oss;
	oss << "(" << pnt.x() << "," << pnt.y() << ")";

	return oss.str();
}
