#include "pch.h"
#include "LayoutNet.h"
#include "geometry.h"
#include "MyCGAL.hpp"
#include "cgalUtilities.h"
#include "MyUtilities.h"

using namespace meta_impl;
class LayoutNet::Impl
{
public:
	Impl()
	{
		_pl.attach(_arr);
	}

	Impl(const Impl& src)
		: _arr(src._arr)
		, _pl(src._pl)
	{
		_pl.attach(_arr);
	}

	void clear()
	{
		_arr.clear();
		_id_vertex_map.clear();
		_id_halfedge_map.clear();
		_id_face_map.clear();
	}

	void refresh_idmap()
	{
		// Clear existing ID maps
		_id_vertex_map.clear();
		_id_halfedge_map.clear();
		_id_face_map.clear();

		// Refresh vertex ID map
		for (auto vit = _arr.vertices_begin(); vit != _arr.vertices_end(); ++vit)
		{
			int id = static_cast<int>(std::hash<Arr_Vertex_handle>()(vit));
			_id_vertex_map[id] = vit;
		}

		// Refresh halfedge ID map
		for (auto heit = _arr.halfedges_begin(); heit != _arr.halfedges_end(); ++heit)
		{
			int id = static_cast<int>(std::hash<Arr_Halfedge_handle>()(heit));
			_id_halfedge_map[id] = heit;
		}

		// Refresh face ID map
		for (auto fit = _arr.faces_begin(); fit != _arr.faces_end(); ++fit)
		{
			int id = static_cast<int>(std::hash<Arr_Face_handle>()(fit));
			_id_face_map[id] = fit;
		}
	}

	bool find_vertex(Arr_Vertex_handle& handle, int id) const
	{
		std::unordered_map<int, Arr_Vertex_handle>::const_iterator it = _id_vertex_map.find(id);
		if (it == _id_vertex_map.end())
			return false;

		handle = it->second;
		return true;
	}

	bool is_vertex(int id) const
	{
		std::unordered_map<int, Arr_Vertex_handle>::const_iterator it = _id_vertex_map.find(id);
		if (it == _id_vertex_map.end())
			return false;
		return true;
	}

	bool find_halfedge(Arr_Halfedge_handle& handle, int id) const
	{
		std::unordered_map<int, Arr_Halfedge_handle>::const_iterator it = _id_halfedge_map.find(id);
		if (it == _id_halfedge_map.end())
			return false;

		handle = it->second;
		return true;
	}

	bool is_halfedge(int id) const
	{
		std::unordered_map<int, Arr_Halfedge_handle>::const_iterator it = _id_halfedge_map.find(id);
		if (it == _id_halfedge_map.end())
			return false;
		return true;
	}

	bool find_face(Arr_Face_handle& handle, int id) const
	{
		std::unordered_map<int, Arr_Face_handle>::const_iterator it = _id_face_map.find(id);
		if (it == _id_face_map.end())
			return false;

		handle = it->second;
		return true;
	}

	bool is_face(int id) const
	{
		std::unordered_map<int, Arr_Face_handle>::const_iterator it = _id_face_map.find(id);
		if (it == _id_face_map.end())
			return false;
		return true;
	}

	Arrangement_2& arr()
	{
		return _arr;
	}

	const Arrangement_2& arr() const
	{
		return _arr;
	}

	Arr_Pointlocation& pl()
	{
		return _pl;
	}

	const Arr_Pointlocation& pl() const
	{
		return _pl;
	}

private:
	Arrangement_2 _arr;
	Arr_Pointlocation _pl;

	std::unordered_map<int, Arr_Vertex_handle> _id_vertex_map;
	std::unordered_map<int, Arr_Halfedge_handle> _id_halfedge_map;
	std::unordered_map<int, Arr_Face_handle> _id_face_map;
};

LayoutNet::LayoutNet()
	: _impl(new Impl())
{

}

LayoutNet::LayoutNet(const LayoutNet& src)
	: _impl(new Impl(*src._impl))
{

}

LayoutNet::~LayoutNet()
{
	delete _impl;
}

LayoutNet& LayoutNet::operator=(const LayoutNet& src)
{
	*_impl = *src._impl;
	return *this;
}

void LayoutNet::clear()
{
	_impl->clear();
}

void LayoutNet::insert(const Polygon2d& polygon)
{
	int size = polygon.pointSize();
	for (int i = 0; i < size; ++i)
	{
		const Point2d& sp = polygon.point(i);
		const Point2d& ep = polygon.point(i + 1 == size ? 0 : (i + 1));

		Arr_Segment_2 segment(Point_2(sp.x, sp.y), Point_2(ep.x, ep.y));
		CGAL::insert(_impl->arr(), segment, _impl->pl());
	}
}

void* LayoutNet::arrangement()
{
	return static_cast<void*>(&_impl->arr());
}

const void* LayoutNet::arrangement() const
{
	return static_cast<void*>(&_impl->arr());
}

void LayoutNet::refresh_idmap()
{
	_impl->refresh_idmap();
}

Topology* LayoutNet::get(int id) const
{
	Arr_Vertex_handle vertex_handle;
	if (_impl->find_vertex(vertex_handle, id))
	{
		return new Vertex(static_cast<void*>(&vertex_handle));
	}

	Arr_Halfedge_handle he_handle;
	if (_impl->find_halfedge(he_handle, id))
	{
		return new Halfedge(static_cast<void*>(&he_handle));
	}

	Arr_Face_handle face_handle;
	if (_impl->find_face(face_handle, id))
	{
		return new Face(static_cast<void*>(&face_handle));
	}

	return nullptr;
}

Topology::TopologyType LayoutNet::type(int id) const
{
	if (_impl->is_vertex(id))
		return Topology::emVertex;
	else if (_impl->is_halfedge(id))
		return Topology::emHalfedge;
	else if (_impl->is_face(id))
		return Topology::emFace;

	return Topology::emNone;
}

Vertex LayoutNet::getVertex(int id) const
{
	Arr_Vertex_handle handle;
	if (_impl->find_vertex(handle, id))
	{
		return Vertex(static_cast<void*>(&handle));
	}

	return Vertex();
}

Halfedge LayoutNet::getHalfedge(int id) const
{
	Arr_Halfedge_handle handle;
	if (_impl->find_halfedge(handle, id))
	{
		return Halfedge(static_cast<void*>(&handle));
	}

	return Halfedge();
}

Face LayoutNet::getFace(int id) const
{
	Arr_Face_handle handle;
	if (_impl->find_face(handle, id))
	{
		return Face(static_cast<void*>(&handle));
	}

	return Face();
}

Topology* LayoutNet::find(const Point2d& pnt, const MyTol& tol)
{
	Arr_topology_item ret = _impl->pl().locate(Point_2(pnt.x, pnt.y));
	switch (ret.which())
	{
	case 0:
		break;
	case 1:
	{
		Arr_Halfedge_const_handle he = boost::get<Arr_Halfedge_const_handle>(ret);
		if (he.ptr() != nullptr)
		{
			return new Edge(static_cast<void*>(&he));
		}
	}
		break;
	case 2:
	{
		Arr_Face_const_handle face = boost::get<Arr_Face_const_handle>(ret);
		if (face.ptr() != nullptr)
		{
			Arr_Halfedge_handle he1;
			if (cgalUtilities::is_on_edge(he1, Arr_Face_handle(const_cast<Arr_Face*>(face.ptr())), Point_2(pnt.x, pnt.y), tol))
			{
				return new Edge(static_cast<void*>(&he1));
			}

			return new Face(static_cast<void*>(&face));
		}
	}
		break;
	default:
		break;
	}

	return nullptr;
}

void LayoutNet::outmostLoop(Polygon2d& loop) const
{
	// 清空 loop 以确保它是空的
	loop.clear();

	// 通过 unbounded_face() 获取无界面
	const Arr_Face_const_handle& outer_face = _impl->arr().unbounded_face();
	if (outer_face->number_of_inner_ccbs() > 0)
	{
		// 假设只有一个内边界
		auto inner_ccb = outer_face->inner_ccbs_begin();

		// 获取无界面的内边界
		Arrangement_2::Ccb_halfedge_const_circulator circ = *inner_ccb;
		Arrangement_2::Ccb_halfedge_const_circulator start = circ;

		std::vector<Point2d> points;
		do
		{
			const Point_2& source = circ->source()->point();
			points.emplace_back(source.x(), source.y());
			++circ;
		} while (circ != start);

		// 如果需要逆时针顺序，反转点的顺序
		std::reverse(points.begin(), points.end());

		// 添加点到 loop
		for (const auto& point : points)
		{
			loop.push_back(point);
		}
	}
}

int LayoutNet::vertexCount() const
{
	return (int)_impl->arr().number_of_vertices();
}

VertexIterator LayoutNet::vertexBegin() const
{
	Arrangement_2::Vertex_iterator it = _impl->arr().vertices_begin();
	return VertexIterator(static_cast<void*>(&it));
}

VertexIterator LayoutNet::vertexEnd() const
{
	Arrangement_2::Vertex_iterator it = _impl->arr().vertices_end();
	return VertexIterator(static_cast<void*>(&it));
}

int LayoutNet::halfedgeCount() const
{
	return (int)_impl->arr().number_of_halfedges();
}

HalfedgeIterator LayoutNet::halfedgeBegin() const
{
	Arrangement_2::Halfedge_iterator it = _impl->arr().halfedges_begin();
	return HalfedgeIterator(static_cast<void*>(&it));
}

HalfedgeIterator LayoutNet::halfedgeEnd() const
{
	Arrangement_2::Halfedge_iterator it = _impl->arr().halfedges_end();
	return HalfedgeIterator(static_cast<void*>(&it));
}

int LayoutNet::edgeCount() const
{
	return (int)_impl->arr().number_of_edges();
}

EdgeIterator LayoutNet::edgeBegin() const
{
	Arrangement_2::Edge_iterator it = _impl->arr().edges_begin();
	return EdgeIterator(static_cast<void*>(&it));
}

EdgeIterator LayoutNet::edgeEnd() const
{
	Arrangement_2::Edge_iterator it = _impl->arr().edges_end();
	return EdgeIterator(static_cast<void*>(&it));
}

int LayoutNet::faceCount() const
{
	return (int)_impl->arr().number_of_faces();
}

FaceIterator LayoutNet::faceBegin() const
{
	Arr_Face_iterator it = _impl->arr().faces_begin();
	return FaceIterator(static_cast<void*>(&it));
}

FaceIterator LayoutNet::faceEnd() const 
{
	Arr_Face_iterator it = _impl->arr().faces_end();
	return FaceIterator(static_cast<void*>(&it)); 
}

Face LayoutNet::unboundedFace() const
{
	Arr_Face_handle handle = _impl->arr().unbounded_face();
	return Face(static_cast<void*>(&handle));
}

void LayoutNet::test()
{
	Arr_Face_iterator it = _impl->arr().faces_begin();
	for (; it != _impl->arr().faces_end(); ++it)
	{
		Arr_Face_handle handle = it;

		char buffer[64];
#if defined(_WIN32)
		sprintf_s(buffer, sizeof(buffer), "Pointer address: %p\n", (const void*)handle.ptr());
		OutputDebugStringA(buffer);
#else
		std::snprintf(buffer, sizeof(buffer), "Pointer address: %p\n", (const void*)handle.ptr());
		std::fprintf(stderr, "%s", buffer);
#endif
	}
}
