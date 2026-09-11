#pragma once
#include "topology.h"

namespace meta_impl
{
	class LayoutNet
	{
	public:
		MODELLING_EXIMPORT LayoutNet();
		MODELLING_EXIMPORT LayoutNet(const LayoutNet& src);
		MODELLING_EXIMPORT ~LayoutNet();
		MODELLING_EXIMPORT LayoutNet& operator=(const LayoutNet& src);

		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT void insert(const meta_impl::Polygon2d& polygon);

		MODELLING_EXIMPORT void* arrangement();
		MODELLING_EXIMPORT const void* arrangement() const;

		MODELLING_EXIMPORT void refresh_idmap();
		MODELLING_EXIMPORT Topology* get(int id) const;
		MODELLING_EXIMPORT Topology::TopologyType type(int id) const;
		MODELLING_EXIMPORT Vertex getVertex(int id) const;
		MODELLING_EXIMPORT Halfedge getHalfedge(int id) const;
		MODELLING_EXIMPORT Face getFace(int id) const;

		MODELLING_EXIMPORT Topology* find(const meta_impl::Point2d& pnt, 
			const meta_impl::MyTol& tol = meta_impl::MyTol::dTol); // 返回对象需外部释放
		MODELLING_EXIMPORT void outmostLoop(meta_impl::Polygon2d& loop) const;

		MODELLING_EXIMPORT int vertexCount() const;
		MODELLING_EXIMPORT VertexIterator vertexBegin() const;
		MODELLING_EXIMPORT VertexIterator vertexEnd() const;

		MODELLING_EXIMPORT int halfedgeCount() const;
		MODELLING_EXIMPORT HalfedgeIterator halfedgeBegin() const;
		MODELLING_EXIMPORT HalfedgeIterator halfedgeEnd() const;

		MODELLING_EXIMPORT int edgeCount() const;
		MODELLING_EXIMPORT EdgeIterator edgeBegin() const;
		MODELLING_EXIMPORT EdgeIterator edgeEnd() const;

		MODELLING_EXIMPORT int faceCount() const;
		MODELLING_EXIMPORT FaceIterator faceBegin() const;
		MODELLING_EXIMPORT FaceIterator faceEnd() const;
		MODELLING_EXIMPORT Face unboundedFace() const;

		MODELLING_EXIMPORT void test();

	private:
		class Impl;
		Impl* _impl;
	};
} // namespace meta_impl


