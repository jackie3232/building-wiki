#pragma once

namespace meta_impl
{
	class MyTol
	{
	public:
		MODELLING_EXIMPORT MyTol();
		MODELLING_EXIMPORT MyTol(double equalPnt, double equalVec);

		MODELLING_EXIMPORT static MyTol dTol;

		MODELLING_EXIMPORT void setEqualPoint(double tol);
		MODELLING_EXIMPORT double equalPoint() const;

		MODELLING_EXIMPORT void setEqualVector(double tol);
		MODELLING_EXIMPORT double equalVector() const;

	private:
		double _equalPoint;
		double _equalVector;
	};

	class Point
	{
	public:
		MODELLING_EXIMPORT Point();
		MODELLING_EXIMPORT Point(double x, double y, double z);
		MODELLING_EXIMPORT void set(double x, double y, double z);

		MODELLING_EXIMPORT static Point Origin;
		double x;
		double y;
		double z;
	};

	class Vector2d;
	class Point2d
	{
	public:
		MODELLING_EXIMPORT Point2d();
		MODELLING_EXIMPORT Point2d(double x, double y);

		MODELLING_EXIMPORT double distance(const Point2d& another) const;
		MODELLING_EXIMPORT Point2d nearest(const Point2d& pnt1, const Point2d& pnt2) const;
		MODELLING_EXIMPORT double distanceTo(const Point2d& another) const;
		MODELLING_EXIMPORT bool isEqualTo(const Point2d& another, const MyTol& tol = MyTol::dTol) const;
		MODELLING_EXIMPORT void transformBy(const Vector2d& offset);

		MODELLING_EXIMPORT Point2d operator-(const Vector2d& vec) const;
		MODELLING_EXIMPORT Vector2d operator-(const Point2d& pnt) const;
		MODELLING_EXIMPORT Point2d operator+(const Point2d& pnt) const;
		MODELLING_EXIMPORT Point2d operator+(const Vector2d& vec) const;

		MODELLING_EXIMPORT static Point2d Origin;
		double x;
		double y;
	};

	class Point2ds
	{
	public:
		MODELLING_EXIMPORT Point2ds();
		MODELLING_EXIMPORT Point2ds(const Point2ds& src);
		MODELLING_EXIMPORT ~Point2ds();

		MODELLING_EXIMPORT int push_back(const Point2d& point);
		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT int size() const;

		MODELLING_EXIMPORT Point2ds& operator=(const Point2ds& src);
		MODELLING_EXIMPORT Point2d& operator[](int n);
		MODELLING_EXIMPORT const Point2d& operator[](int n) const;

	private:
		class Impl;
		Impl* _impl;
	};

	class Vector
	{
	public:
		MODELLING_EXIMPORT Vector();
		MODELLING_EXIMPORT Vector(double x, double y, double z);

		MODELLING_EXIMPORT static Vector XVector;
		MODELLING_EXIMPORT static Vector YVector;
		MODELLING_EXIMPORT static Vector ZVector;

		MODELLING_EXIMPORT double length() const;
		MODELLING_EXIMPORT Vector operator-(const Vector& vec) const;

		double x;
		double y;
		double z;
	};

	class Direction2d;
	class Vector2d
	{
	public:
		MODELLING_EXIMPORT Vector2d();
		MODELLING_EXIMPORT Vector2d(double x, double y);

		MODELLING_EXIMPORT Vector2d& normalize(const MyTol& tol = MyTol::dTol);
		MODELLING_EXIMPORT Vector2d normal(const MyTol& tol = MyTol::dTol) const;
		MODELLING_EXIMPORT double dot(const Vector2d& vec) const;
		MODELLING_EXIMPORT double lengthSquared() const;
		MODELLING_EXIMPORT Vector2d perpendicular() const;
		MODELLING_EXIMPORT double length() const;
		MODELLING_EXIMPORT Direction2d toDirection() const;
		MODELLING_EXIMPORT void rotateBy(double radian);

		MODELLING_EXIMPORT bool isPerpendicularTo(const Vector2d& vec, const MyTol& tol = MyTol::dTol) const;
		MODELLING_EXIMPORT bool isParallelTo(const Vector2d& vec, const MyTol& tol = MyTol::dTol) const;
		MODELLING_EXIMPORT bool isCodirectionalTo(const Vector2d& vec, const MyTol& tol = MyTol::dTol) const;

		MODELLING_EXIMPORT Vector2d operator+(const Vector2d& vec) const;
		MODELLING_EXIMPORT Vector2d operator-(const Vector2d& vec) const;
		MODELLING_EXIMPORT Vector2d operator* (double d) const;

		MODELLING_EXIMPORT static Vector2d XVector;
		MODELLING_EXIMPORT static Vector2d YVector;

		double x;
		double y;
	};

	class Direction
	{
	public:
		MODELLING_EXIMPORT Direction();
		MODELLING_EXIMPORT Direction(double x, double y, double z);
		MODELLING_EXIMPORT void set(double x, double y, double z);

		MODELLING_EXIMPORT static Direction XAxis;
		MODELLING_EXIMPORT static Direction YAxis;
		MODELLING_EXIMPORT static Direction ZAxis;

		MODELLING_EXIMPORT void normalize(double& x, double& y, double& z);
		MODELLING_EXIMPORT bool isEqualTo(const Direction& direction, const MyTol& tol = MyTol::dTol) const;
		MODELLING_EXIMPORT Direction crossProduct(const Direction& another) const;

		double x;
		double y;
		double z;
	};

	class Direction2d
	{
	public:
		MODELLING_EXIMPORT Direction2d();
		MODELLING_EXIMPORT Direction2d(double x, double y);

		MODELLING_EXIMPORT static Direction2d XAxis;
		MODELLING_EXIMPORT static Direction2d YAxis;

		MODELLING_EXIMPORT Direction2d& normalize(const MyTol& tol = MyTol::dTol);
		MODELLING_EXIMPORT Vector2d toVector() const;
		MODELLING_EXIMPORT bool isEqualTo(const Direction2d& direction, const MyTol& tol = MyTol::dTol) const;
		MODELLING_EXIMPORT Direction2d rotate(double radian) const;
		MODELLING_EXIMPORT void rotateBy(double radian);
		MODELLING_EXIMPORT Direction2d perpDirection() const; // 垂直向量，逆时针旋转90度

		MODELLING_EXIMPORT Direction2d operator-(const Direction2d& d) const;
		MODELLING_EXIMPORT Vector2d operator*(double length) const;

		double x;
		double y;
	};

	class Matrix3d
	{
	public:
		MODELLING_EXIMPORT Matrix3d();
		MODELLING_EXIMPORT static Matrix3d dIdentity;

		Point origin;
		Direction xaxis;
		Direction yaxis;
		Direction zaxis;
	};

	class Curve2d
	{
	public:
		enum CurveType
		{
			emCurve,
			emLine,
			emCircle,
			emSegment,
			emLineSegment,
			emCircArc,
			emPolygon
		};
		MODELLING_EXIMPORT virtual ~Curve2d();

		MODELLING_EXIMPORT static CurveType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(CurveType objType) const;
		MODELLING_EXIMPORT virtual CurveType type() const = 0;

		MODELLING_EXIMPORT static Curve2d* copy(const Curve2d* src); // 需要外部释放
		MODELLING_EXIMPORT virtual Curve2d* copy() const = 0; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Curve2d* src) = 0;

		MODELLING_EXIMPORT virtual double distanceTo(const Point2d& pnt) const = 0;
		MODELLING_EXIMPORT virtual Point2d closestPointTo(const Point2d& pnt) const = 0;

	protected:
		Curve2d();
		Curve2d(const Curve2d& src);
		Curve2d& operator=(const Curve2d& src);
	};

	class Circle2d;
	class Line2d
		: public Curve2d
	{
	public:
		MODELLING_EXIMPORT Line2d();
		MODELLING_EXIMPORT Line2d(const Line2d& src);
		MODELLING_EXIMPORT Line2d(const Point2d& sp, const Point2d& ep);
		MODELLING_EXIMPORT ~Line2d();
		MODELLING_EXIMPORT Line2d& operator=(const Line2d& src);

		MODELLING_EXIMPORT static CurveType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(CurveType objType) const;
		MODELLING_EXIMPORT virtual CurveType type() const;

		MODELLING_EXIMPORT virtual Curve2d* copy() const;
		MODELLING_EXIMPORT virtual void copyFrom(const Curve2d* src);

		MODELLING_EXIMPORT virtual double distanceTo(const Point2d& pnt) const;
		MODELLING_EXIMPORT virtual Point2d closestPointTo(const Point2d& pnt) const;

		MODELLING_EXIMPORT void setPoint(Point2d pnt);
		MODELLING_EXIMPORT Point2d point() const;

		MODELLING_EXIMPORT void setDirection(Direction2d dir);
		MODELLING_EXIMPORT Direction2d direction() const;

		MODELLING_EXIMPORT bool intersectWith(Point2d& pnt, const Line2d& line) const;
		MODELLING_EXIMPORT int intersectWith(Point2d& pnt1, Point2d& pnt2, const Circle2d& circle) const;

	private:
		Point2d _pnt;
		Direction2d _dir;
	};

	class Circle2d
		:public Curve2d
	{
	public:
		MODELLING_EXIMPORT Circle2d();
		MODELLING_EXIMPORT Circle2d(const Circle2d& src);
		MODELLING_EXIMPORT Circle2d(const Point2d& center, double radius);
		MODELLING_EXIMPORT ~Circle2d();
		MODELLING_EXIMPORT Circle2d& operator=(const Circle2d& src);

		MODELLING_EXIMPORT static CurveType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(CurveType objType) const;
		MODELLING_EXIMPORT virtual CurveType type() const;

		MODELLING_EXIMPORT virtual Curve2d* copy() const;
		MODELLING_EXIMPORT virtual void copyFrom(const Curve2d* src);

		MODELLING_EXIMPORT virtual double distanceTo(const Point2d& pnt) const;
		MODELLING_EXIMPORT virtual Point2d closestPointTo(const Point2d& pnt) const;

		MODELLING_EXIMPORT void setCenter(Point2d pnt);
		MODELLING_EXIMPORT Point2d center() const;

		MODELLING_EXIMPORT void setRadius(double radius);
		MODELLING_EXIMPORT double radius() const;

		MODELLING_EXIMPORT int intersectWith(Point2d& pnt1, Point2d& pnt2, const Line2d& line) const;
		MODELLING_EXIMPORT int intersectWith(Point2d& pnt1, Point2d& pnt2, const Circle2d& circle) const;

	private:
		Point2d _center;
		double _radius;
	};

	class Segment2d
		: public Curve2d
	{
	public:
		MODELLING_EXIMPORT ~Segment2d();

		MODELLING_EXIMPORT static CurveType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(CurveType objType) const;

		MODELLING_EXIMPORT void setStart(Point2d p);
		MODELLING_EXIMPORT Point2d start() const;

		MODELLING_EXIMPORT void setEnd(Point2d p);
		MODELLING_EXIMPORT Point2d end() const;

		MODELLING_EXIMPORT virtual void extendFromStart(double length) = 0;
		MODELLING_EXIMPORT virtual void extendFromEnd(double lenght) = 0;

		MODELLING_EXIMPORT virtual void offset(double distance) = 0;
		MODELLING_EXIMPORT virtual Point2d midPoint() const = 0;
		MODELLING_EXIMPORT virtual double length() const = 0;

	protected:
		Segment2d();
		Segment2d(const Segment2d& src);
		Segment2d(const Point2d& sp, const Point2d& ep);
		Segment2d(const Point2d& sp, const Point2d& ep, double bulge);
		Segment2d& operator=(const Segment2d& src);

		Point2d _sp;
		Point2d _ep;
		double _bulge;
	};

	class LineSegment2d :
		public Segment2d
	{
	public:
		MODELLING_EXIMPORT LineSegment2d();
		MODELLING_EXIMPORT LineSegment2d(const LineSegment2d& src);
		MODELLING_EXIMPORT LineSegment2d(const Point2d& sp, const Point2d& ep);
		MODELLING_EXIMPORT ~LineSegment2d();
		MODELLING_EXIMPORT LineSegment2d& operator=(const LineSegment2d& src);

		MODELLING_EXIMPORT static CurveType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(CurveType objType) const;
		MODELLING_EXIMPORT virtual CurveType type() const;

		MODELLING_EXIMPORT virtual Curve2d* copy() const;
		MODELLING_EXIMPORT virtual void copyFrom(const Curve2d* src);

		MODELLING_EXIMPORT virtual double distanceTo(const Point2d& pnt) const;
		MODELLING_EXIMPORT virtual Point2d closestPointTo(const Point2d& pnt) const;

		MODELLING_EXIMPORT virtual void extendFromStart(double length);
		MODELLING_EXIMPORT virtual void extendFromEnd(double length);

		MODELLING_EXIMPORT virtual void offset(double distance); // distance为正向右偏移
		MODELLING_EXIMPORT virtual Point2d midPoint() const;
		MODELLING_EXIMPORT virtual double length() const;

		MODELLING_EXIMPORT Vector2d vector() const;
		MODELLING_EXIMPORT Direction2d direction() const;
		MODELLING_EXIMPORT LineSegment2d& resetBasedOnMiddle(double length); // 以中点向前后重新设置
		MODELLING_EXIMPORT Line2d line() const;
	};

	class CircArc2d :
		public Segment2d
	{
	public:
		MODELLING_EXIMPORT CircArc2d();
		MODELLING_EXIMPORT CircArc2d(const CircArc2d& src);
		MODELLING_EXIMPORT CircArc2d(const Point2d& sp, const Point2d& ep, double bulge);
		MODELLING_EXIMPORT ~CircArc2d();
		MODELLING_EXIMPORT CircArc2d& operator=(const CircArc2d& src);

		MODELLING_EXIMPORT static CurveType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(CurveType objType) const;
		MODELLING_EXIMPORT virtual CurveType type() const;

		MODELLING_EXIMPORT virtual Curve2d* copy() const;
		MODELLING_EXIMPORT virtual void copyFrom(const Curve2d* src);

		MODELLING_EXIMPORT virtual double distanceTo(const Point2d& pnt) const;
		MODELLING_EXIMPORT virtual Point2d closestPointTo(const Point2d& pnt) const;

		MODELLING_EXIMPORT virtual void extendFromStart(double length) {};
		MODELLING_EXIMPORT virtual void extendFromEnd(double lenght) {};

		MODELLING_EXIMPORT void setBulge(double bulge);
		MODELLING_EXIMPORT double bulge() const;
		MODELLING_EXIMPORT virtual void offset(double distance);
		MODELLING_EXIMPORT virtual Point2d midPoint() const;
		MODELLING_EXIMPORT virtual double length() const;

		MODELLING_EXIMPORT Point2d center() const;
		MODELLING_EXIMPORT double radius() const;

		MODELLING_EXIMPORT static double calculateBulge(const Point2d& sp, const Point2d& ep, const Point2d& center);
	};

	class Polygon2d : 
		public Curve2d
	{
	public:
		enum PointStatus
		{
			emError,
			emInner,
			emOn,
			emOuter
		};

		MODELLING_EXIMPORT Polygon2d();
		MODELLING_EXIMPORT Polygon2d(const Polygon2d& src);
		MODELLING_EXIMPORT Polygon2d(const Point2d& left_bottom, const Point2d& right_top);
		MODELLING_EXIMPORT ~Polygon2d();

		MODELLING_EXIMPORT static CurveType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(CurveType objType) const;
		MODELLING_EXIMPORT virtual CurveType type() const;

		MODELLING_EXIMPORT virtual Curve2d* copy() const;
		MODELLING_EXIMPORT virtual void copyFrom(const Curve2d* src);

		MODELLING_EXIMPORT virtual double distanceTo(const Point2d& pnt) const; // 内部点 - 负值；线上点 - 0；外部点 - 正值
		MODELLING_EXIMPORT virtual Point2d closestPointTo(const Point2d& pnt) const;

		MODELLING_EXIMPORT void push_back(Point2d pnt);
		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT int pointSize() const;
		MODELLING_EXIMPORT Point2d& point(int n);
		MODELLING_EXIMPORT const Point2d& point(int n) const;

		MODELLING_EXIMPORT void mergeCollinear(); // 合并共线（直线段/弧线段）
		MODELLING_EXIMPORT void offset(double distance); // 正值代表向外、负值代表向内
		MODELLING_EXIMPORT Polygon2d& operator = (const Polygon2d& src);

		MODELLING_EXIMPORT bool unionWith(const Polygon2d& other);
		MODELLING_EXIMPORT bool subtract(const Polygon2d& other);
		MODELLING_EXIMPORT PointStatus pointStatus(const Point2d& pnt, const MyTol& tol = MyTol::dTol) const;
		MODELLING_EXIMPORT Point2d pointInsidePolygon() const; // 内部任意点
		MODELLING_EXIMPORT void transformBy(const Vector2d& offset);

		MODELLING_EXIMPORT static bool areCollinear(Point2d p1, Point2d p2, Point2d p3, const MyTol& tol = MyTol::dTol);

	private:
		Point2ds _points;
	};
} // namespace meta_impl
