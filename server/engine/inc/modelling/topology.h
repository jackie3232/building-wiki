#pragma once
#include "geometry.h"

namespace meta_impl
{
	class LayoutNet;
	class Topology
	{
	public:
		enum TopologyType
		{
			emNone,
			emVertex,
			emHalfedge,
			emEdge,
			emFace,
		};

		virtual ~Topology() {}
		virtual TopologyType type() const = 0;

		virtual int id() const = 0;
		virtual void* pointer() const = 0;
		virtual void* handle() const = 0;
		virtual bool isNull() const = 0;

	protected:
		Topology();
		int _id;
	};

	class Halfedge;
	class HalfedgeCirculator;
	class Vertex :
		public Topology
	{
	public:
		MODELLING_EXIMPORT Vertex();
		MODELLING_EXIMPORT Vertex(void* handle); // 接受 void* 以隐藏具体类型
		MODELLING_EXIMPORT ~Vertex();
		MODELLING_EXIMPORT Vertex(const Vertex& other);
		MODELLING_EXIMPORT virtual TopologyType type() const;

		MODELLING_EXIMPORT virtual int id() const;
		MODELLING_EXIMPORT virtual void* pointer() const;
		MODELLING_EXIMPORT virtual void* handle() const;
		MODELLING_EXIMPORT virtual bool isNull() const;

		MODELLING_EXIMPORT Vertex& operator=(const Vertex& other);
		MODELLING_EXIMPORT bool operator==(const Vertex& other);

		// 获取顶点的坐标
		MODELLING_EXIMPORT meta_impl::Point2d point() const;
		MODELLING_EXIMPORT int degree() const; // 相连的边数
		MODELLING_EXIMPORT HalfedgeCirculator incident_halfedges() const; // 所有指向当前vertex的顺时针排列的半边

	private:
		class Impl;
		Impl* impl_;
	};

	class VertexIterator
	{
	public:
		MODELLING_EXIMPORT VertexIterator();
		MODELLING_EXIMPORT VertexIterator(void* it); // 接受 void* 以隐藏具体类型
		MODELLING_EXIMPORT ~VertexIterator();
		MODELLING_EXIMPORT VertexIterator(const VertexIterator& other);
		MODELLING_EXIMPORT VertexIterator& operator=(const VertexIterator& other);

		MODELLING_EXIMPORT VertexIterator& operator++(); // 前置++
		MODELLING_EXIMPORT VertexIterator operator++(int); // 后置++
		MODELLING_EXIMPORT bool operator!=(const VertexIterator& other) const;
		MODELLING_EXIMPORT bool operator==(const VertexIterator& other) const;
		MODELLING_EXIMPORT Vertex operator*() const;

	private:
		class Impl;
		Impl* impl_;
	};

	class Face;
	class Edge :
		public Topology
	{
	public:
		MODELLING_EXIMPORT Edge();
		MODELLING_EXIMPORT Edge(void* handle); // 接受 void* 以隐藏具体类型
		MODELLING_EXIMPORT ~Edge();
		MODELLING_EXIMPORT Edge(const Edge& other);
		MODELLING_EXIMPORT virtual TopologyType type() const;

		MODELLING_EXIMPORT virtual int id() const;
		MODELLING_EXIMPORT virtual void* pointer() const;
		MODELLING_EXIMPORT virtual void* handle() const;
		MODELLING_EXIMPORT virtual bool isNull() const;

		MODELLING_EXIMPORT Edge& operator=(const Edge& other);
		MODELLING_EXIMPORT bool operator==(const Edge& other);

		// 获取两个端点（与获取的Curve起终点可能不一致！）
		MODELLING_EXIMPORT Vertex vertex1() const;
		MODELLING_EXIMPORT Vertex vertex2() const;

		// 获取两个半边
		MODELLING_EXIMPORT Halfedge halfedge1() const;
		MODELLING_EXIMPORT Halfedge halfedge2() const;

		MODELLING_EXIMPORT Face face1() const;
		MODELLING_EXIMPORT Face face2() const;

		MODELLING_EXIMPORT Edge oppsite() const;

		// 获取curve
		MODELLING_EXIMPORT meta_impl::LineSegment2d curve() const;
		MODELLING_EXIMPORT double length() const;

	private:
		class Impl;
		Impl* impl_;
	};

	class EdgeArray
	{
	public:
		MODELLING_EXIMPORT EdgeArray();
		MODELLING_EXIMPORT EdgeArray(const EdgeArray& src);
		MODELLING_EXIMPORT ~EdgeArray();

		MODELLING_EXIMPORT void push_back(const Edge& edge);
		MODELLING_EXIMPORT const Edge& edge(int n) const;
		MODELLING_EXIMPORT int size() const;
		MODELLING_EXIMPORT void clear();

		MODELLING_EXIMPORT const Edge& operator[](int n) const;
		MODELLING_EXIMPORT void operator=(const EdgeArray& src);

	private:
		class Impl;
		Impl* impl_;
	};

	class EdgeIterator
	{
	public:
		MODELLING_EXIMPORT EdgeIterator();
		MODELLING_EXIMPORT EdgeIterator(void* it); // 接受 void* 以隐藏具体类型
		MODELLING_EXIMPORT ~EdgeIterator();
		MODELLING_EXIMPORT EdgeIterator(const EdgeIterator& other);
		MODELLING_EXIMPORT EdgeIterator& operator=(const EdgeIterator& other);

		MODELLING_EXIMPORT EdgeIterator& operator++(); // 前置++
		MODELLING_EXIMPORT EdgeIterator operator++(int); // 后置++
		MODELLING_EXIMPORT bool operator!=(const EdgeIterator& other) const;
		MODELLING_EXIMPORT bool operator==(const EdgeIterator& other) const;
		MODELLING_EXIMPORT Edge operator*() const;

	private:
		class Impl;
		Impl* impl_;
	};

	class Face;
	class Halfedge :
		public Topology
	{
	public:
		MODELLING_EXIMPORT Halfedge();
		MODELLING_EXIMPORT Halfedge(void* handle); // 接受 void* 以隐藏具体类型
		MODELLING_EXIMPORT ~Halfedge();
		MODELLING_EXIMPORT Halfedge(const Halfedge& other);
		MODELLING_EXIMPORT virtual TopologyType type() const;

		MODELLING_EXIMPORT virtual int id() const;
		MODELLING_EXIMPORT virtual void* pointer() const;
		MODELLING_EXIMPORT virtual void* handle() const;
		MODELLING_EXIMPORT virtual bool isNull() const;

		MODELLING_EXIMPORT Halfedge& operator=(const Halfedge& other);
		MODELLING_EXIMPORT bool operator==(const Halfedge& other);

		MODELLING_EXIMPORT Vertex source() const;
		MODELLING_EXIMPORT Vertex target() const;

		MODELLING_EXIMPORT Face face() const;
		MODELLING_EXIMPORT Edge edge() const;

		MODELLING_EXIMPORT Halfedge twin() const;
		MODELLING_EXIMPORT Halfedge next() const;
		MODELLING_EXIMPORT Halfedge prev() const;

		MODELLING_EXIMPORT meta_impl::LineSegment2d curve() const;

	private:
		class Impl;
		Impl* impl_;
	};

	class HalfedgeIterator
	{
	public:
		MODELLING_EXIMPORT HalfedgeIterator();
		MODELLING_EXIMPORT HalfedgeIterator(void* it); // 接受 void* 以隐藏具体类型
		MODELLING_EXIMPORT ~HalfedgeIterator();
		MODELLING_EXIMPORT HalfedgeIterator(const HalfedgeIterator& other);
		MODELLING_EXIMPORT HalfedgeIterator& operator=(const HalfedgeIterator& other);

		MODELLING_EXIMPORT HalfedgeIterator& operator++(); // 前置++
		MODELLING_EXIMPORT HalfedgeIterator operator++(int); // 后置++
		MODELLING_EXIMPORT bool operator!=(const HalfedgeIterator& other) const;
		MODELLING_EXIMPORT bool operator==(const HalfedgeIterator& other) const;
		MODELLING_EXIMPORT Halfedge operator*() const;

	private:
		class Impl;
		Impl* impl_;
	};

	class HalfedgeCirculator
	{
	public:
		MODELLING_EXIMPORT HalfedgeCirculator();
		MODELLING_EXIMPORT HalfedgeCirculator(void* handle); // 接受 void* 以隐藏具体类型
		MODELLING_EXIMPORT ~HalfedgeCirculator();
		MODELLING_EXIMPORT HalfedgeCirculator(const HalfedgeCirculator& other);
		MODELLING_EXIMPORT HalfedgeCirculator& operator=(const HalfedgeCirculator& other);

		MODELLING_EXIMPORT HalfedgeCirculator& operator++(); // 前置++
		MODELLING_EXIMPORT HalfedgeCirculator operator++(int); // 后置++
		MODELLING_EXIMPORT bool operator!=(const HalfedgeCirculator& other) const;
		MODELLING_EXIMPORT bool operator==(const HalfedgeCirculator& other) const;
		MODELLING_EXIMPORT Halfedge operator*() const;

	private:
		class Impl;
		Impl* impl_;
	};

	class Face :
		public Topology
	{
	public:
		MODELLING_EXIMPORT Face();
		MODELLING_EXIMPORT Face(void* handle);  // 修改：接受 void* 以隐藏具体类型
		MODELLING_EXIMPORT Face(const Face& other);
		MODELLING_EXIMPORT ~Face();
		MODELLING_EXIMPORT virtual TopologyType type() const;

		MODELLING_EXIMPORT virtual int id() const;
		MODELLING_EXIMPORT virtual void* pointer() const;
		MODELLING_EXIMPORT virtual void* handle() const;
		MODELLING_EXIMPORT virtual bool isNull() const;

		MODELLING_EXIMPORT Face& operator=(const Face& other);
		MODELLING_EXIMPORT bool operator==(const Face& other);

		// 获取外部半边循环
		MODELLING_EXIMPORT Halfedge outerHalfedge() const;
		MODELLING_EXIMPORT int outerHalfedgeNumber() const;

		// 面是否为无限面
		MODELLING_EXIMPORT bool isUnbounded() const;
		MODELLING_EXIMPORT meta_impl::Polygon2d outerLoop() const;

	private:
		class Impl;
		Impl* impl_;
	};

	class FaceIterator
	{
	public:
		MODELLING_EXIMPORT FaceIterator();
		MODELLING_EXIMPORT ~FaceIterator();
		MODELLING_EXIMPORT FaceIterator(void* it);
		MODELLING_EXIMPORT FaceIterator(const FaceIterator& other);
		MODELLING_EXIMPORT FaceIterator& operator=(const FaceIterator& other);

		MODELLING_EXIMPORT FaceIterator& operator++(); // 前置++
		MODELLING_EXIMPORT FaceIterator operator++(int); // 后置++
		MODELLING_EXIMPORT bool operator!=(const FaceIterator& other) const;
		MODELLING_EXIMPORT bool operator==(const FaceIterator& other) const;
		MODELLING_EXIMPORT Face operator*() const;

	private:
		class Impl;
		Impl* impl_;
	};
} // namespace meta_impl

