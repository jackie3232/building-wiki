#include "pch.h"
#include "topology.h"
#include "MyCGAL.hpp"
#include <boost/optional.hpp>
#include "cgalUtilities.h"
#include "IdCreator.h"

using namespace meta_impl;

Topology::Topology()
	: _id(IdCreator::singleton().create())
{

}

int Topology::id() const
{
	return _id;
}

class Vertex::Impl 
{
public:
	Arr_Vertex_handle handle;

	Impl() {}
	Impl(Arr_Vertex_handle handle) : handle(handle) {}
};

// Vertex 实现
Vertex::Vertex() 
    : impl_(new Impl())
{

}

Vertex::Vertex(void* handle)
	: impl_(new Impl(*(static_cast<Arr_Vertex_handle*>(handle))))
{

}

Topology::TopologyType Vertex::type() const
{
	return Topology::emVertex;
}

int Vertex::id() const
{
	return (int)std::hash<Arr_Vertex_handle>()(impl_->handle);
}

void* Vertex::pointer() const
{
	return static_cast<void*>(impl_->handle.ptr());
}

void* Vertex::handle() const
{
	return static_cast<void*>(&impl_->handle);
}

bool Vertex::isNull() const
{
	if (impl_ == nullptr || impl_->handle.ptr() == nullptr)
		return true;
	return false;
}

Vertex& Vertex::operator=(const Vertex& other)
{
	if (this != &other)
	{
		impl_->handle = other.impl_->handle;
	}
	return *this;
}

bool Vertex::operator==(const Vertex& other)
{
	return impl_->handle == other.impl_->handle;
}

meta_impl::Point2d Vertex::point() const
{
	Point_2 cgal_point = impl_->handle->point();
	return meta_impl::Point2d(cgal_point.x(), cgal_point.y());
}

int Vertex::degree() const
{
    return (int)impl_->handle->degree();
}

HalfedgeCirculator Vertex::incident_halfedges() const
{
	Arr_Halfedge_around_vertex_circulator circulator = impl_->handle->incident_halfedges();
	return HalfedgeCirculator(static_cast<void*>(&circulator));
}

Vertex::~Vertex() 
{ 
    delete impl_;
}

Vertex::Vertex(const Vertex& other) 
    : impl_(new Impl(other.impl_->handle)) 
{

}

class VertexIterator::Impl 
{
public:
	Arr_Vertex_iterator it;

	Impl() {}
	Impl(Arr_Vertex_iterator it) : it(it) {}
};

// VertexIterator 实现
VertexIterator::VertexIterator()
    : impl_(new Impl())
{

}

VertexIterator::VertexIterator(void* it) 
    : impl_(new Impl(*(static_cast<Arr_Vertex_iterator*>(it))))
{

}

VertexIterator::~VertexIterator()
{
    delete impl_;
}

VertexIterator::VertexIterator(const VertexIterator& other)
    : impl_(new Impl(other.impl_->it)) 
{

}

VertexIterator& VertexIterator::operator=(const VertexIterator& other)
{
	if (this != &other) 
    {
		impl_->it = other.impl_->it;
	}
	return *this;
}

VertexIterator& VertexIterator::operator++() 
{
	++(impl_->it);
	return *this;
}

VertexIterator VertexIterator::operator++(int)
{
	VertexIterator temp = *this;
	++(impl_->it);
	return temp;
}

bool VertexIterator::operator!=(const VertexIterator& other) const 
{
	return impl_->it != other.impl_->it;
}

bool VertexIterator::operator==(const VertexIterator& other) const 
{
	return impl_->it == other.impl_->it;
}

Vertex VertexIterator::operator*() const
{
	Arr_Vertex_handle handle = impl_->it;
	return Vertex(static_cast<void*>(&handle));
}


class Edge::Impl
{
public:
	Arr_Halfedge_handle handle;

	Impl() {}
	Impl(Arr_Halfedge_handle halfedge) : handle(halfedge) {}
};

// Edge 实现
Edge::Edge() 
    : impl_(new Impl()) 
{

}

Edge::Edge(void* handle)
	: impl_(new Impl(*(static_cast<Arr_Halfedge_handle*>(handle))))
{

}

Edge::~Edge()
{ 
    delete impl_; 
}

Edge::Edge(const Edge& other)
    : impl_(new Impl(other.impl_->handle))
{

}

Topology::TopologyType Edge::type() const
{
	return Topology::emEdge;
}

int Edge::id() const
{
	return (int)std::hash<Arr_Halfedge_handle>()(impl_->handle);
}

void* Edge::pointer() const
{
	return static_cast<void*>(impl_->handle.ptr());
}

void* Edge::handle() const
{
	return static_cast<void*>(&impl_->handle);
}

bool Edge::isNull() const
{
	if (impl_ == nullptr || impl_->handle.ptr() == nullptr)
		return true;
	return false;
}

Edge& Edge::operator=(const Edge& other)
{
	if (this != &other)
	{
		impl_->handle = other.impl_->handle;
	}
	return *this;
}

bool Edge::operator==(const Edge& other)
{
	return impl_->handle == other.impl_->handle;
}

Vertex Edge::vertex1() const
{
	Arr_Vertex_handle handle = impl_->handle->source();
	return Vertex(static_cast<void*>(&handle));
}

Vertex Edge::vertex2() const
{
	Arr_Vertex_handle handle = impl_->handle->target();
	return Vertex(static_cast<void*>(&handle));
}

Halfedge Edge::halfedge1() const
{
	Arr_Halfedge_handle handle = impl_->handle;
	return Halfedge(static_cast<void*>(&handle));
}

Halfedge Edge::halfedge2() const
{
	Arr_Halfedge_handle handle = impl_->handle->twin();
	return Halfedge(static_cast<void*>(&handle));
}

Face Edge::face1() const
{
	Arr_Halfedge_handle handle = impl_->handle;
	Arr_Face_handle f_handle = handle->face();
	return Face(static_cast<void*>(&f_handle));
}

Face Edge::face2() const
{
	Arr_Halfedge_handle handle = impl_->handle->twin();
	Arr_Face_handle f_handle = handle->face();
	return Face(static_cast<void*>(&f_handle));
}

Edge Edge::oppsite() const
{
	Arr_Halfedge_handle handle = impl_->handle->twin();
	return Edge(static_cast<void*>(&handle));
}

LineSegment2d Edge::curve() const
{
	return cgalUtilities::convert(impl_->handle->curve());
}

double Edge::length() const
{
	const Arr_Segment_2& segment = impl_->handle->curve();
	return cgalUtilities::length(segment);
}

class EdgeArray::Impl
{
public:
	std::vector<Edge> edges;
};

EdgeArray::EdgeArray()
	: impl_(new Impl())
{

}

EdgeArray::EdgeArray(const EdgeArray& src)
	: impl_(new Impl(*src.impl_))
{

}

EdgeArray::~EdgeArray()
{
	delete impl_;
}

void EdgeArray::push_back(const Edge& edge)
{
	impl_->edges.push_back(edge);
}

const Edge& EdgeArray::edge(int n) const
{
	return impl_->edges[n];
}

int EdgeArray::size() const
{
	return (int)impl_->edges.size();
}

void EdgeArray::clear()
{
	impl_->edges.clear();
}

const Edge& EdgeArray::operator[](int n) const
{
	return impl_->edges[n];
}

void EdgeArray::operator=(const EdgeArray& src)
{
	*impl_ = *src.impl_;
}

class EdgeIterator::Impl
{
public:
	Arr_Edge_iterator it;

	Impl() {}
	Impl(Arr_Edge_iterator it) : it(it) {}
};

// EdgeIterator 实现
EdgeIterator::EdgeIterator()
	: impl_(new Impl())
{

}

EdgeIterator::EdgeIterator(void* it)
	: impl_(new Impl(*(static_cast<Arr_Edge_iterator*>(it))))
{

}

EdgeIterator::~EdgeIterator()
{
	delete impl_;
}

EdgeIterator::EdgeIterator(const EdgeIterator& other)
	: impl_(new Impl(other.impl_->it))
{

}

EdgeIterator& EdgeIterator::operator=(const EdgeIterator& other)
{
	if (this != &other)
	{
		impl_->it = other.impl_->it;
	}
	return *this;
}

EdgeIterator& EdgeIterator::operator++()
{
	++(impl_->it);
	return *this;
}

EdgeIterator EdgeIterator::operator++(int)
{
	EdgeIterator temp = *this;
	++(impl_->it);
	return temp;
}

bool EdgeIterator::operator!=(const EdgeIterator& other) const
{
	return impl_->it != other.impl_->it;
}

bool EdgeIterator::operator==(const EdgeIterator& other) const
{
	return impl_->it == other.impl_->it;
}

Edge EdgeIterator::operator*() const
{
	Arr_Halfedge_handle handle = impl_->it;
	return Edge(static_cast<void*>(&handle));
}


class Halfedge::Impl
{
public:
    Arr_Halfedge_handle handle;

    Impl() {}
    Impl(Arr_Halfedge_handle handle) : handle(handle) {}
};

// Halfedge 实现
Halfedge::Halfedge() 
    : impl_(new Impl())
{

}

Halfedge::Halfedge(void* handle) 
	: impl_(new Impl(*(static_cast<Arr_Halfedge_handle*>(handle))))
{

}

Halfedge::~Halfedge() 
{ 
    delete impl_;
}

Halfedge::Halfedge(const Halfedge& other) 
    : impl_(new Impl(other.impl_->handle))
{

}

Topology::TopologyType Halfedge::type() const
{
	return Topology::emHalfedge;
}

int Halfedge::id() const
{
	return (int)std::hash<Arr_Halfedge_handle>()(impl_->handle);
}

void* Halfedge::pointer() const
{
	return static_cast<void*>(impl_->handle.ptr());
}

void* Halfedge::handle() const
{
	return static_cast<void*>(&impl_->handle);
}

bool Halfedge::isNull() const
{
	if (impl_ == nullptr || impl_->handle.ptr() == nullptr)
		return true;
	return false;
}

Halfedge& Halfedge::operator=(const Halfedge& other)
{
	if (this != &other)
	{
		impl_->handle = other.impl_->handle;
	}
	return *this;
}

bool Halfedge::operator==(const Halfedge& other)
{
	return impl_->handle == other.impl_->handle;
}

Vertex Halfedge::source() const
{
	Arr_Vertex_handle handle = impl_->handle->source();
	return Vertex(static_cast<void*>(&handle));
}

Vertex Halfedge::target() const
{
	Arr_Vertex_handle handle = impl_->handle->target();
	return Vertex(static_cast<void*>(&handle));
}

Face Halfedge::face() const 
{
	Arr_Face_handle handle = impl_->handle->face();
	return Face(static_cast<void*>(&handle));
}

Edge Halfedge::edge() const
{
	return Edge(static_cast<void*>(&impl_->handle));
}

Halfedge Halfedge::twin() const
{
	Arr_Halfedge_handle handle = impl_->handle->twin();
	return Halfedge(static_cast<void*>(&handle));
}

Halfedge Halfedge::next() const
{
	Arr_Halfedge_handle handle = impl_->handle->next();
	return Halfedge(static_cast<void*>(&handle));
}

Halfedge Halfedge::prev() const 
{
	Arr_Halfedge_handle handle = impl_->handle->prev();
	return Halfedge(static_cast<void*>(&handle));
}

LineSegment2d Halfedge::curve() const
{
	return cgalUtilities::convert(impl_->handle->curve());
}

class HalfedgeIterator::Impl 
{
public:
    Arr_Halfedge_iterator it;

    Impl() {}
    Impl(Arr_Halfedge_iterator it) : it(it) {}
};

// HalfedgeIterator 实现
HalfedgeIterator::HalfedgeIterator() 
    : impl_(new Impl())
{

}

HalfedgeIterator::HalfedgeIterator(void* it) 
    : impl_(new Impl(*(static_cast<Arr_Halfedge_iterator*>(it))))
{

}

HalfedgeIterator::~HalfedgeIterator() 
{ 
    delete impl_; 
}

HalfedgeIterator::HalfedgeIterator(const HalfedgeIterator& other) 
    : impl_(new Impl(other.impl_->it))
{

}

HalfedgeIterator& HalfedgeIterator::operator=(const HalfedgeIterator& other) 
{
    if (this != &other)
    {
        impl_->it = other.impl_->it;
    }
    return *this;
}

HalfedgeIterator& HalfedgeIterator::operator++()
{
    ++(impl_->it);
    return *this;
}

HalfedgeIterator HalfedgeIterator::operator++(int) 
{
    HalfedgeIterator temp = *this;
    ++(impl_->it);
    return temp;
}

bool HalfedgeIterator::operator!=(const HalfedgeIterator& other) const
{
    return impl_->it != other.impl_->it;
}

bool HalfedgeIterator::operator==(const HalfedgeIterator& other) const 
{
    return impl_->it == other.impl_->it;
}

Halfedge HalfedgeIterator::operator*() const 
{
	Arr_Halfedge_handle handle = impl_->it;
    return Halfedge(static_cast<void*>(&handle));
}

class HalfedgeCirculator::Impl
{
public:
	Arr_Halfedge_around_vertex_circulator circ;

	Impl() {}
	Impl(Arr_Halfedge_around_vertex_circulator circ) : circ(circ) {}
};

// HalfedgeCirculator 实现
HalfedgeCirculator::HalfedgeCirculator()
	: impl_(new Impl())
{
}

HalfedgeCirculator::HalfedgeCirculator(void* handle)
	: impl_(new Impl(*(static_cast<Arr_Halfedge_around_vertex_circulator*>(handle))))
{
}

HalfedgeCirculator::~HalfedgeCirculator()
{
	delete impl_;
}

HalfedgeCirculator::HalfedgeCirculator(const HalfedgeCirculator& other)
	: impl_(new Impl(other.impl_->circ))
{
}

HalfedgeCirculator& HalfedgeCirculator::operator=(const HalfedgeCirculator& other)
{
	if (this != &other)
	{
		impl_->circ = other.impl_->circ;
	}
	return *this;
}

HalfedgeCirculator& HalfedgeCirculator::operator++()
{
	++(impl_->circ);
	return *this;
}

HalfedgeCirculator HalfedgeCirculator::operator++(int)
{
	HalfedgeCirculator temp = *this;
	++(impl_->circ);
	return temp;
}

bool HalfedgeCirculator::operator!=(const HalfedgeCirculator& other) const
{
	return impl_->circ != other.impl_->circ;
}

bool HalfedgeCirculator::operator==(const HalfedgeCirculator& other) const
{
	return impl_->circ == other.impl_->circ;
}

Halfedge HalfedgeCirculator::operator*() const
{
	Arr_Halfedge_handle handle = impl_->circ;
	return Halfedge(static_cast<void*>(&handle));
}

class Face::Impl
{
public:
    Arr_Face_handle handle;

    Impl() {}
    Impl(Arr_Face_handle handle) : handle(handle) {}
};

Face::Face() 
    : impl_(new Impl())
{

}

Face::Face(void* handle)
    : impl_(new Impl(*(static_cast<Arr_Face_handle*>(handle)))) 
{

}

Face::Face(const Face& other) 
    : impl_(new Impl(other.impl_->handle)) 
{

}

Face::~Face() 
{ 
    delete impl_; 
}

Topology::TopologyType Face::type() const
{
	return Topology::emFace;
}

int Face::id() const
{
	return (int)std::hash<Arr_Face_handle>()(impl_->handle);
}

void* Face::pointer() const
{
	return static_cast<void*>(impl_->handle.ptr());
}

void* Face::handle() const
{
	return static_cast<void*>(&impl_->handle);
}

bool Face::isNull() const
{
	if (impl_ == nullptr || impl_->handle.ptr() == nullptr)
		return true;
	return false;
}

Face& Face::operator=(const Face& other)
{
	if (this != &other) {
		impl_->handle = other.impl_->handle;
	}
	return *this;
}

bool Face::operator==(const Face& other)
{
	return impl_->handle == other.impl_->handle;
}

Halfedge Face::outerHalfedge() const 
{
	if (impl_->handle->has_outer_ccb()) 
    {
		Arr_Halfedge_handle handle = impl_->handle->outer_ccb();
		return Halfedge(static_cast<void*>(&handle));
	}
	return Halfedge();
}

int Face::outerHalfedgeNumber() const
{
	// 半边循环的迭代器  
	Arrangement_2::Ccb_halfedge_circulator it = impl_->handle->outer_ccb();

	// 初始化计数器  
	int count = 0;

	// 遍历外部半边循环并计数  
	do 
	{
		++count; // 增加计数  
		++it; // 移动到下一个半边  
	} while (it != impl_->handle->outer_ccb()); // 遍历直到回到起始半边  

	return count; // 返回半边数量
}

bool Face::isUnbounded() const 
{
	return impl_->handle->is_unbounded();
}


Polygon2d Face::outerLoop() const
{
	if (impl_->handle->is_unbounded())
		return Polygon2d();

	Polygon2d polygon;
	Arrangement_2::Ccb_halfedge_circulator it = impl_->handle->outer_ccb();
	do
	{
		Arr_Halfedge_handle he = it;
		Point_2 pnt = he->source()->point();
		polygon.push_back(Point2d(pnt.x(), pnt.y()));

	} while (++it != impl_->handle->outer_ccb()); // 遍历直到回到起始半边

	return polygon;
}

class FaceIterator::Impl 
{
public:
    Arr_Face_iterator it;

    Impl() {}
    Impl(Arr_Face_iterator it) : it(it) {}
};

FaceIterator::FaceIterator() 
    : impl_(new Impl())
{

}

FaceIterator::~FaceIterator() 
{ 
    delete impl_; 
}

FaceIterator::FaceIterator(void* it) 
    : impl_(new Impl(*(static_cast<Arr_Face_iterator*>(it)))) 
{

}

FaceIterator::FaceIterator(const FaceIterator& other) 
    : impl_(new Impl(other.impl_->it)) 
{

}
FaceIterator& FaceIterator::operator=(const FaceIterator& other)
{
    if (this != &other) 
    {
        impl_->it = other.impl_->it;
    }
    return *this;
}

FaceIterator& FaceIterator::operator++() 
{
    ++(impl_->it);
    return *this;
}

FaceIterator FaceIterator::operator++(int)
{
    FaceIterator temp = *this;
    ++(impl_->it);
    return temp;
}

bool FaceIterator::operator!=(const FaceIterator& other) const
{
    return impl_->it != other.impl_->it;
}

bool FaceIterator::operator==(const FaceIterator& other) const
{
    return impl_->it == other.impl_->it;
}

Face FaceIterator::operator*() const 
{
	Arr_Face_handle handle = impl_->it;
    return Face(static_cast<void*>(&handle));
}
