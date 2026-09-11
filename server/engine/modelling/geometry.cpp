#include "pch.h"
#include "geometry.h"
#include <valarray>
#include <vector>
#include "MyCGAL.hpp"
#if defined(_MSC_VER)
#include <corecrt_math_defines.h>
#else
#ifndef _USE_MATH_DEFINES
#define _USE_MATH_DEFINES
#endif
#include <cmath>
#endif
#include <CGAL/Boolean_set_operations_2.h>
#include "cgalUtilities.h"

using namespace meta_impl;
MyTol MyTol::dTol;
MyTol::MyTol()
	: _equalPoint(0.5)
	, _equalVector(0.00000001)
{

}

MyTol::MyTol(double equalPnt, double equalVec)
	: _equalPoint(equalPnt)
	, _equalVector(equalVec)
{

}

void MyTol::setEqualPoint(double tol)
{
	_equalPoint = tol;
}

double MyTol::equalPoint() const
{
	return _equalPoint;
}

void MyTol::setEqualVector(double tol)
{
	_equalVector = tol;
}

double MyTol::equalVector() const
{
	return _equalVector;
}

class Points 
{
public:
	std::vector<Point> points;
};

Point Point::Origin;
Point::Point()
	: x(0), y(0), z(0)
{

}

Point::Point(double x_, double y_, double z_)
	: x(x_), y(y_), z(z_)
{

}

void Point::set(double x_, double y_, double z_)
{
	x = x_;
	y = y_;
	z = z_;
}

Point2d Point2d::Origin;
Point2d::Point2d()
	: x(0), y(0)
{

}

Point2d::Point2d(double x_, double y_)
	: x(x_), y(y_)
{

}

double Point2d::distance(const Point2d& another) const
{
	return sqrt((another.x - x) * (another.x - x) + (another.y - y) * (another.y - y));
}

Point2d Point2d::nearest(const Point2d& pnt1, const Point2d& pnt2) const
{
	double dist1 = this->distanceTo(pnt1);
	double dist2 = this->distanceTo(pnt2);

	return (dist1 < dist2) ? pnt1 : pnt2;
}

double Point2d::distanceTo(const Point2d& another) const
{
	double dx = x - another.x;
	double dy = y - another.y;
	return std::sqrt(dx * dx + dy * dy);
}

bool Point2d::isEqualTo(const Point2d& another, const MyTol& tol) const
{
	return (*this - another).length() <= tol.equalPoint();
}

void Point2d::transformBy(const Vector2d& offset)
{
	x += offset.x; // 将向量的 x 分量加到点的 x 坐标  
	y += offset.y; // 将向量的 y 分量加到点的 y 坐标
}

Point2d Point2d::operator-(const Vector2d& vec) const
{
	return Point2d(x - vec.x, y - vec.y);
}

Vector2d Point2d::operator-(const Point2d& pnt) const
{
	return Vector2d(x - pnt.x, y - pnt.y);
}

Point2d Point2d::operator+(const Point2d& pnt) const
{
	return Point2d(x + pnt.x, y + pnt.y);
}

Point2d Point2d::operator+(const Vector2d& vec) const
{
	return Point2d(x + vec.x, y + vec.y);
}

class Point2ds::Impl
{
public:
	void clear()
	{
		_points.clear();
	}

	int push_back(const Point2d& point)
	{
		_points.push_back(point);
		int index = int(_points.size() - 1);

		return index;
	}

	int size() const
	{
		return (int)_points.size();
	}

	Point2d& operator[](int n)
	{
		return _points[n];
	}

	const Point2d& operator[](int n) const
	{
		return _points[n];
	}

private:
	std::vector<Point2d> _points;
};

Point2ds::Point2ds()
	: _impl(new Impl())
{

}

Point2ds::Point2ds(const Point2ds& src)
	: _impl(new Impl(*src._impl))
{

}

Point2ds::~Point2ds()
{
	delete _impl;
}

int Point2ds::push_back(const Point2d& point)
{
	return _impl->push_back(point);
}

void Point2ds::clear()
{
	_impl->clear();
}

int Point2ds::size() const
{
	return _impl->size();
}

Point2ds& Point2ds::operator=(const Point2ds& src)
{
	*_impl = *src._impl;
	return *this;
}

Point2d& Point2ds::operator[](int n)
{
	return (*_impl)[n];
}

const Point2d& Point2ds::operator[](int n) const
{
	return (*_impl)[n];
}

Vector Vector::XVector(1, 0, 0);
Vector Vector::YVector(0, 1, 0);
Vector Vector::ZVector(0, 0, 1);
Vector::Vector()
	: x(0), y(0), z(0)
{

}

Vector::Vector(double x_, double y_, double z_)
	: x(x_), y(y_), z(z_)
{

}

double Vector::length() const
{
	return std::sqrt(x * x + y * y + z * z);
}

Vector Vector::operator-(const Vector& vec) const
{
	return Vector(x - vec.x, y - vec.y, z - vec.z);
}

Vector2d Vector2d::XVector(1, 0);
Vector2d Vector2d::YVector(0, 1);
Vector2d::Vector2d()
	: x(0), y(0)
{

}

Vector2d::Vector2d(double x_, double y_)
	: x(x_), y(y_)
{

}

Vector2d& Vector2d::normalize(const MyTol& tol)
{
	double length = std::sqrt(x * x + y * y);
	if (length < tol.equalPoint())
		return *this;
	
	x /= length;
	y /= length;

	return *this;
}

Vector2d Vector2d::normal(const MyTol& tol) const
{
	double length = std::sqrt(x * x + y * y);
	if (length < tol.equalPoint())
		return *this;

	double x_ = x;
	double y_ = y;

	x_ /= length;
	y_ /= length;

	return Vector2d(x_, y_);
}

double Vector2d::dot(const Vector2d& other) const
{
	return this->x * other.x + this->y * other.y;
}

double Vector2d::lengthSquared() const
{
	return x * x + y * y;
}

Vector2d Vector2d::perpendicular() const
{
	return Vector2d(-y, x);
}

double Vector2d::length() const
{
	return std::sqrt(x * x + y * y);
}

Direction2d Vector2d::toDirection() const
{
	return Direction2d(x, y);
}

void Vector2d::rotateBy(double radian)
{
	// 计算旋转后的坐标  
	double rotatedX = x * cos(radian) - y * sin(radian);
	double rotatedY = x * sin(radian) + y * cos(radian);

	x = rotatedX;
	y = rotatedY;
}

bool Vector2d::isPerpendicularTo(const Vector2d& vec, const MyTol& tol) const
{
	// 计算长度  
	double length1 = this->length();
	double length2 = vec.length();

	// 检查是否有零长度向量  
	if (length1 == 0.0 || length2 == 0.0) 
	{
		return false; // 如果任一向量长度为零，则不认为它们是垂直的  
	}

	// 计算点积  
	double dotProduct = this->dot(vec);

	// 计算绝对值并与容差比较  
	double ratio = std::abs(dotProduct) / (length1 * length2);

	return ratio <= tol.equalVector(); // 使用 equalVector() 方法进行比较
}

bool Vector2d::isParallelTo(const Vector2d& vec, const MyTol& tol) const
{
	// 归一化两个向量  
	Vector2d norm1 = this->normal();
	Vector2d norm2 = vec.normal();

	// 计算归一化向量的差和和  
	Vector2d diff = norm1 - norm2;
	Vector2d sum = norm1 + norm2;

	// 检查长度是否在容差范围内  
	return (diff.length() < tol.equalVector() || sum.length() < tol.equalVector());
}

bool Vector2d::isCodirectionalTo(const Vector2d& vec, const MyTol& tol) const
{
	Direction2d dir1 = this->toDirection();
	Direction2d dir2 = vec.toDirection();

	return dir1.isEqualTo(dir2, tol);
}

Vector2d Vector2d::operator+(const Vector2d& vec) const
{
	return Vector2d(x + vec.x, y + vec.y);
}

Vector2d Vector2d::operator-(const Vector2d& vec) const
{
	return Vector2d(x - vec.x, y - vec.y);
}

Vector2d Vector2d::operator*(double d) const
{
	return Vector2d(x * d, y * d);
}

Direction Direction::XAxis(1, 0, 0);
Direction Direction::YAxis(0, 1, 0);
Direction Direction::ZAxis(0, 0, 1);
Direction::Direction()
	: x(0), y(0), z(0)
{

}

Direction::Direction(double x_, double y_, double z_)
{
	x = x_;
	y = y_;
	z = z_;
	normalize(x_, y_, z_);
}

void Direction::set(double x_, double y_, double z_)
{
	x = x_;
	y = y_;
	z = z_;
	normalize(x, y, z);
}

void Direction::normalize(double& x, double& y, double& z)
{
	double length = std::sqrt(x * x + y * y + z * z);
	if (length > 0)
	{
		x /= length;
		y /= length;
		z /= length;
	}
}

bool Direction::isEqualTo(const Direction& direction, const MyTol& tol) const
{
	// 计算当前方向与传入方向的差  
	Vector diff = Vector(this->x, this->y, this->z) - Vector(direction.x, direction.y, direction.z);

	// 检查差的长度是否小于等于容差  
	return diff.length() <= tol.equalVector();
}

Direction Direction::crossProduct(const Direction& another) const
{
	// 计算叉乘  
	double crossX = this->y * another.z - this->z * another.y;
	double crossY = this->z * another.x - this->x * another.z;
	double crossZ = this->x * another.y - this->y * another.x;

	// 返回新的 Direction 对象  
	return Direction(crossX, crossY, crossZ);
}

Direction2d Direction2d::XAxis(1, 0);
Direction2d Direction2d::YAxis(0, 1);
Direction2d::Direction2d()
	: x(0), y(0)
{

}

Direction2d::Direction2d(double x_, double y_)
	: x(x_)
	, y(y_)
{
	normalize();
}

Direction2d& Direction2d::normalize(const MyTol& tol)
{
	double length = std::sqrt(x * x + y * y);
	if (length < tol.equalPoint())
		return *this;

	x /= length;
	y /= length;

	return *this;
}

Vector2d Direction2d::toVector() const
{
	return Vector2d(x, y);
}

bool Direction2d::isEqualTo(const Direction2d& direction, const MyTol& tol) const
{
	// 计算当前方向与传入方向的差  
	Vector2d diff = Vector2d(this->x, this->y) - Vector2d(direction.x, direction.y);

	// 检查差的长度是否小于等于容差  
	return diff.length() <= tol.equalVector();
}

Direction2d Direction2d::rotate(double radian) const
{
	// 计算旋转后的坐标  
	double rotatedX = x * cos(radian) - y * sin(radian);
	double rotatedY = x * sin(radian) + y * cos(radian);

	return Direction2d(rotatedX, rotatedY);
}

void Direction2d::rotateBy(double radian)
{
	// 计算旋转后的坐标  
	double rotatedX = x * cos(radian) - y * sin(radian);
	double rotatedY = x * sin(radian) + y * cos(radian);
	
	x = rotatedX;
	y = rotatedY;
}

Direction2d Direction2d::perpDirection() const
{
	return Direction2d(-y, x);
}

Direction2d Direction2d::operator-(const Direction2d& d) const
{
	return Direction2d(x - d.x, y - d.y);
}

Vector2d Direction2d::operator*(double length) const
{
	return Vector2d(x * length, y * length);
}

Matrix3d Matrix3d::dIdentity;
Matrix3d::Matrix3d()
	: origin(0, 0, 0)
	, xaxis(1, 0, 0)
	, yaxis(0, 1, 0)
	, zaxis(0, 0, 1)
{

}

Curve2d::Curve2d()
{

}

Curve2d::Curve2d(const Curve2d& src)
{

}

Curve2d::~Curve2d()
{

}

Curve2d& Curve2d::operator=(const Curve2d& src)
{
	return *this;
}

Curve2d::CurveType Curve2d::desc()
{
	return Curve2d::emCurve;
}

bool Curve2d::isKindOf(CurveType objType) const
{
	if (objType == Curve2d::emCurve)
		return true;
	return false;
}

Curve2d* Curve2d::copy(const Curve2d* src)
{
	return src->copy();
}

Line2d::Line2d()
	: Curve2d()
{

}

Line2d::Line2d(const Line2d& src)
	: Curve2d(src)
{

}

Line2d::Line2d(const Point2d& sp, const Point2d& ep)
	: Curve2d()
	, _pnt(sp)
	, _dir((ep - sp).toDirection())
{

}

Line2d::~Line2d()
{

}

Line2d& Line2d::operator=(const Line2d& src)
{
	Curve2d::operator=(src);
	_pnt = src._pnt;
	_dir = src._dir;
	return *this;
}

Curve2d::CurveType Line2d::desc()
{
	return CurveType::emLine;
}

bool Line2d::isKindOf(CurveType objType) const
{
	if (objType == Curve2d::emLine)
		return true;
	return Curve2d::isKindOf(objType);
}

Curve2d::CurveType Line2d::type() const
{
	return CurveType::emLine;
}

Curve2d* Line2d::copy() const
{
	return new Line2d(*this);
}

void Line2d::copyFrom(const Curve2d* src)
{
	*this = *static_cast<const Line2d*>(src);
}

double Line2d::distanceTo(const Point2d& pnt) const
{
	Point_2 pnt_(pnt.x, pnt.y);
	Line_2 line(Point_2(_pnt.x, _pnt.y), Direction_2(_dir.x,_dir.y));

	double sqrd_dist = CGAL::squared_distance(line, pnt_);
	return sqrt(sqrd_dist);
}

void Line2d::setPoint(Point2d pnt)
{
	_pnt = pnt;
}

Point2d Line2d::point() const
{
	return _pnt;
}

void Line2d::setDirection(Direction2d dir)
{
	_dir = dir;
}

Direction2d Line2d::direction() const
{
	return _dir;
}

bool Line2d::intersectWith(Point2d& pnt, const Line2d& line) const
{
	// 获取两条线的方向向量  
	Vector2d dir1 = this->direction().toVector();
	Vector2d dir2 = line.direction().toVector();

	// 计算行列式（实际上是叉积的z分量）  
	double det = dir1.x * dir2.y - dir1.y * dir2.x;

	// 如果行列式为0，说明线平行或重合，无交点  
	if (std::abs(det) < 1e-8)  // 使用一个小的阈值来处理浮点数精度问题  
		return false;

	// 获取两条线上的点  
	Point2d p1 = this->point();
	Point2d p2 = line.point();

	// 计算两点之间的向量  
	Vector2d diff = p2 - p1;

	// 计算参数 t1 和 t2  
	double t1 = (diff.x * dir2.y - diff.y * dir2.x) / det;

	// 计算交点  
	pnt = p1 + dir1 * t1;

	return true;
}

int Line2d::intersectWith(Point2d& pnt1, Point2d& pnt2, const Circle2d& circle) const
{
	// 获取直线上的一点和方向向量  
	Point2d linePoint = this->point();
	Vector2d lineDir = this->direction().toVector();

	// 获取圆心和半径  
	Point2d center = circle.center();
	double radius = circle.radius();

	// 计算直线上离圆心最近的点  
	Vector2d toCenter = center - linePoint;
	double t = toCenter.dot(lineDir);
	Point2d closestPoint = linePoint + lineDir * t;

	// 计算最近点到圆心的距离  
	double distanceSquared = (closestPoint - center).lengthSquared();
	double radiusSquared = radius * radius;

	if (distanceSquared > radiusSquared) {
		// 没有交点  
		return 0;
	}
	else if (std::abs(distanceSquared - radiusSquared) < 1e-6) {
		// 一个交点（切点）  
		pnt1 = closestPoint;
		return 1;
	}
	else {
		// 两个交点  
		double distanceToIntersection = std::sqrt(radiusSquared - distanceSquared);
		pnt1 = closestPoint - lineDir * distanceToIntersection;
		pnt2 = closestPoint + lineDir * distanceToIntersection;
		return 2;
	}
}

Point2d Line2d::closestPointTo(const Point2d& pnt) const
{
	Line_2 line(Point_2(_pnt.x, _pnt.y), Direction_2(_dir.x, _dir.y));
	Point_2 prj = line.projection(Point_2(pnt.x, pnt.y));
	return Point2d(prj.x(), prj.y());
}

Circle2d::Circle2d()
	: Curve2d()
	, _center()
	, _radius(0)
{

}

Circle2d::Circle2d(const Circle2d& src)
	: Curve2d(src)
	, _center(src._center)
	, _radius(src._radius)
{

}

Circle2d::Circle2d(const Point2d& center, double radius)
	: Curve2d()
	, _center(center)
	, _radius(radius)
{

}

Circle2d::~Circle2d()
{

}

Circle2d& Circle2d::operator=(const Circle2d& src)
{
	Curve2d::operator=(src);
	_center = src._center;
	_radius = src._radius;
	return *this;
}

Curve2d::CurveType Circle2d::desc()
{
	return CurveType::emCircle;
}

bool Circle2d::isKindOf(CurveType objType) const
{
	if (objType == Curve2d::emCircle)
		return true;
	return Curve2d::isKindOf(objType);
}

Curve2d::CurveType Circle2d::type() const
{
	return CurveType::emCircle;
}

Curve2d* Circle2d::copy() const
{
	return new Circle2d(*this);
}

void Circle2d::copyFrom(const Curve2d* src)
{
	*this = *static_cast<const Circle2d*>(src);
}

double Circle2d::distanceTo(const Point2d& pnt) const
{
	throw std::logic_error("方法未完成！");
}

Point2d Circle2d::closestPointTo(const Point2d& pnt) const
{
	throw std::logic_error("方法未完成！");
}

void Circle2d::setCenter(Point2d pnt)
{
	_center = pnt;
}

Point2d Circle2d::center() const
{
	return _center;
}

void Circle2d::setRadius(double radius)
{
	_radius = radius;
}

double Circle2d::radius() const
{
	return _radius;
}

int Circle2d::intersectWith(Point2d& pnt1, Point2d& pnt2, const Line2d& line) const
{
	return line.intersectWith(pnt1, pnt2, *this);
}

int Circle2d::intersectWith(Point2d& pnt1, Point2d& pnt2, const Circle2d& circle) const
{
	// 计算两个圆心之间的距离  
	double dx = _center.x - circle._center.x;
	double dy = _center.y - circle._center.y;
	double dist = std::sqrt(dx * dx + dy * dy);

	// 两个圆的半径之和  
	double r1 = _radius;
	double r2 = circle._radius;

	// 如果圆心距离大于半径之和，没有交点  
	if (dist > r1 + r2)
		return 0;

	// 如果一个圆包含另一个圆，没有交点  
	if (dist < std::abs(r1 - r2))
		return 0;

	// 如果两个圆完全重合，无穷多个交点，我们返回-1  
	if (dist == 0 && r1 == r2)
		return -1;

	// 计算交点  
	double a = (r1 * r1 - r2 * r2 + dist * dist) / (2 * dist);
	double h = std::sqrt(r1 * r1 - a * a);

	// 交点的中点  
	double x2 = _center.x + a * (circle._center.x - _center.x) / dist;
	double y2 = _center.y + a * (circle._center.y - _center.y) / dist;

	// 计算两个交点  
	pnt1.x = x2 + h * (circle._center.y - _center.y) / dist;
	pnt1.y = y2 - h * (circle._center.x - _center.x) / dist;

	pnt2.x = x2 - h * (circle._center.y - _center.y) / dist;
	pnt2.y = y2 + h * (circle._center.x - _center.x) / dist;

	// 如果两个圆相切，只有一个交点  
	if (dist == r1 + r2 || dist == std::abs(r1 - r2))
		return 1;

	// 两个交点  
	return 2;
}

void Segment2d::setStart(Point2d p)
{
	_sp = p;
}

Point2d Segment2d::start() const
{
	return _sp;
}

void Segment2d::setEnd(Point2d p)
{
	_ep = p;
}

Point2d Segment2d::end() const
{
	return _ep;
}

Segment2d::Segment2d()
	: Curve2d()
	, _sp()
	, _ep()
	, _bulge(0.0)
{

}

Segment2d::Segment2d(const Segment2d& src)
	: Curve2d(src)
	, _sp(src._sp)
	, _ep(src._ep)
	, _bulge(src._bulge)
{

}

Segment2d::Segment2d(const Point2d& sp, const Point2d& ep)
	: Curve2d()
	, _sp(sp)
	, _ep(ep)
	, _bulge(0.0)
{

}

Segment2d::Segment2d(const Point2d& sp, const Point2d& ep, double bulge)
	: Curve2d()
	, _sp(sp)
	, _ep(ep)
	, _bulge(bulge)
{

}

Segment2d& Segment2d::operator=(const Segment2d& src)
{
	Curve2d::operator=(src);
	_sp = src._sp;
	_ep = src._ep;
	_bulge = src._bulge;
	return *this;
}

Segment2d::~Segment2d()
{

}

Curve2d::CurveType Segment2d::desc()
{
	return CurveType::emSegment;
}

bool Segment2d::isKindOf(CurveType objType) const
{
	if (objType == Curve2d::emSegment)
		return true;
	return Curve2d::isKindOf(objType);
}

LineSegment2d::LineSegment2d()
	: Segment2d()
{

}

LineSegment2d::LineSegment2d(const LineSegment2d& src)
	: Segment2d(src)
{

}

LineSegment2d::LineSegment2d(const Point2d& sp, const Point2d& ep)
	: Segment2d(sp, ep)
{

}

LineSegment2d::~LineSegment2d()
{

}

LineSegment2d& LineSegment2d::operator=(const LineSegment2d& src)
{
	Segment2d::operator=(src);
	return *this;
}

Curve2d::CurveType LineSegment2d::desc()
{
	return CurveType::emLineSegment;
}

bool LineSegment2d::isKindOf(CurveType objType) const
{
	if (objType == Curve2d::emLineSegment)
		return true;
	return Segment2d::isKindOf(objType);
}

Curve2d::CurveType LineSegment2d::type() const
{
	return CurveType::emLineSegment;
}

Curve2d* LineSegment2d::copy() const
{
	return new LineSegment2d(*this);
}

void LineSegment2d::copyFrom(const Curve2d* src)
{
	*this = *static_cast<const LineSegment2d*>(src);
}

double LineSegment2d::distanceTo(const Point2d& pnt) const
{
	Point_2 pnt_(pnt.x, pnt.y);
	Segment_2 seg(Point_2(_sp.x, _sp.y), Point_2(_ep.x, _ep.y));

	double sqrd_dist = CGAL::squared_distance(seg, pnt_);
	return sqrt(sqrd_dist);
}

Point2d LineSegment2d::closestPointTo(const Point2d& pnt) const
{
	throw std::logic_error("方法未完成！");
}

void LineSegment2d::extendFromStart(double length)
{
	// 计算线段的方向向量  
	Vector2d direction = _ep - _sp;

	// 归一化方向向量  
	direction.normalize();

	// 计算新的起点  
	Point2d newStart = _sp - direction * length;

	// 更新起点  
	_sp = newStart;
}

void LineSegment2d::extendFromEnd(double length)
{
	// 计算线段的方向向量  
	Vector2d direction = _ep - _sp;

	// 归一化方向向量  
	direction.normalize();

	// 计算新的终点  
	Point2d newEnd = _ep + direction * length;

	// 更新终点  
	_ep = newEnd;
}

void LineSegment2d::offset(double distance)
{
	// 计算线段的方向向量  
	Vector2d dir(_ep.x - _sp.x, _ep.y - _sp.y);

	// 计算法向量（垂直于线段方向，顺时针旋转90度）  
	Vector2d normal(dir);
	normal.rotateBy(- CGAL_PI / 2);

	// 归一化法向量  
	normal.normalize();

	// 计算偏移向量
	Vector2d offset_vector(distance * normal.x, distance * normal.y);

	// 对起点和终点进行偏移  
	_sp.x += offset_vector.x;
	_sp.y += offset_vector.y;
	_ep.x += offset_vector.x;
	_ep.y += offset_vector.y;
}

Point2d LineSegment2d::midPoint() const
{
	// 计算中点坐标  
	double midX = (_sp.x + _ep.x) / 2.0; // x坐标的平均值  
	double midY = (_sp.y + _ep.y) / 2.0; // y坐标的平均值  

	// 返回中点  
	return Point2d(midX, midY);
}

double LineSegment2d::length() const
{
	return sqrt(pow(_ep.x - _sp.x, 2) + pow(_ep.y - _sp.y, 2));
}

Vector2d LineSegment2d::vector() const
{
	return Vector2d(_ep.x - _sp.x, _ep.y - _sp.y);
}

Direction2d LineSegment2d::direction() const
{
	return Direction2d(_ep.x - _sp.x, _ep.y - _sp.y);
}

LineSegment2d& LineSegment2d::resetBasedOnMiddle(double length)
{
	// 计算中点  
	Point2d mid = midPoint();

	// 计算方向向量  
	Direction2d dir = direction();

	// 计算新的起点和终点  
	double halfLength = length / 2.0;
	_sp.x = mid.x - halfLength * dir.x;
	_sp.y = mid.y - halfLength * dir.y;
	_ep.x = mid.x + halfLength * dir.x;
	_ep.y = mid.y + halfLength * dir.y;

	return *this; // 返回当前对象的引用 
}

Line2d LineSegment2d::line() const
{
	return Line2d(_sp, _ep);
}

CircArc2d::CircArc2d()
	: Segment2d()
{

}

CircArc2d::CircArc2d(const CircArc2d& src)
	: Segment2d(src)
{

}

CircArc2d::CircArc2d(const Point2d& sp, const Point2d& ep, double bulge)
	:Segment2d(sp, ep, bulge)
{

}

CircArc2d::~CircArc2d()
{

}

CircArc2d& CircArc2d::operator=(const CircArc2d& src)
{
	Segment2d::operator=(src);
	return *this;
}

Curve2d::CurveType CircArc2d::desc()
{
	return CurveType::emCircArc;
}

bool CircArc2d::isKindOf(CurveType objType) const
{
	if (objType == Curve2d::emCircArc)
		return true;
	return Segment2d::isKindOf(objType);
}

Curve2d::CurveType CircArc2d::type() const
{
	return CurveType::emCircArc;
}

Curve2d* CircArc2d::copy() const
{
	return new CircArc2d(*this);
}

void CircArc2d::copyFrom(const Curve2d* src)
{
	*this = *static_cast<const CircArc2d*>(src);
}

double CircArc2d::distanceTo(const Point2d& pnt) const
{
	throw std::logic_error("方法未完成！");
}

Point2d CircArc2d::closestPointTo(const Point2d& pnt) const
{
	throw std::logic_error("方法未完成！");
}

void CircArc2d::setBulge(double bulge)
{
	_bulge = bulge;
}

double CircArc2d::bulge() const
{
	return _bulge;
}

void CircArc2d::offset(double distance)
{
	// 获取起点和终点  
	Point2d sp = start();
	Point2d ep = end();

	// 计算圆心  
	Point2d center = this->center();

	// 计算半径  
	double radius = sp.distance(center);

	// 根据凸度和距离决定偏移方向  
	double offsetDistance = (_bulge > 0) ? distance : -distance;

	// 计算新的半径  
	double newRadius = radius + offsetDistance;

	// 计算起点和终点的偏移  
	Vector2d startVector(sp.x - center.x, sp.y - center.y);
	Vector2d endVector(ep.x - center.x, ep.y - center.y);

	startVector.normalize();
	endVector.normalize();

	Point2d newStart(center.x + newRadius * startVector.x,
		center.y + newRadius * startVector.y);
	Point2d newEnd(center.x + newRadius * endVector.x,
		center.y + newRadius * endVector.y);

	// 更新起点和终点  
	setStart(newStart);
	setEnd(newEnd);

	// 计算新的凸度  
	double newBulge = calculateBulge(newStart, newEnd, center);
	setBulge(newBulge);
}

Point2d CircArc2d::midPoint() const
{
	throw std::logic_error("方法未完成！");
}

double CircArc2d::length() const
{
	throw std::logic_error("方法未完成！");
}

Point2d CircArc2d::center() const
{
	// 获取起点和终点  
	Point2d sp = start();
	Point2d ep = end();

	double theta = 4 * atan(_bulge);
	double chord = sp.distance(ep);
	double radius = chord / (2 * sin(theta / 2));

	Point2d midpoint((sp.x + ep.x) / 2, (sp.y + ep.y) / 2);

	double dx = ep.x - sp.x;
	double dy = ep.y - sp.y;
	double normalX = -dy;
	double normalY = dx;
	double length = sqrt(normalX * normalX + normalY * normalY);
	normalX /= length;
	normalY /= length;

	double distToCenter = sqrt(radius * radius - (chord / 2) * (chord / 2));
	if (_bulge < 0) distToCenter = -distToCenter;

	return Point2d(midpoint.x + distToCenter * normalX,
		midpoint.y + distToCenter * normalY);
}

double CircArc2d::radius() const
{
	// 计算弦长的一半  
	double halfChord = (_ep - _sp).length() / 2.0;

	// 计算圆弧的高度  
	double sagitta = std::abs(_bulge) * halfChord;

	// 使用圆弧高度公式计算半径  
	// R = (h^2 + c^2) / (4h)，其中 h 是圆弧高度（sagitta），c 是弦长  
	return (sagitta * sagitta + halfChord * halfChord) / (4.0 * sagitta);
}

double CircArc2d::calculateBulge(const Point2d& sp, const Point2d& ep, const Point2d& center)
{
	double dx = ep.x - sp.x;
	double dy = ep.y - sp.y;
	double chord = std::sqrt(dx * dx + dy * dy);
	double radius = sp.distance(center);
	double sagitta = radius - std::sqrt(radius * radius - chord * chord / 4);
	return 2 * sagitta / chord;
}

Polygon2d::Polygon2d()
	: Curve2d()
	, _points()
{

}

Polygon2d::Polygon2d(const Polygon2d& src)
	: Curve2d(src)
	, _points(src._points)
{

}

Polygon2d::Polygon2d(const Point2d& left_bottom, const Point2d& right_top)
	: Curve2d()
{
	_points.push_back(left_bottom);
	_points.push_back(Point2d(right_top.x, left_bottom.y));
	_points.push_back(right_top);
	_points.push_back(Point2d(left_bottom.x, right_top.y));
}

Polygon2d::~Polygon2d()
{

}

Curve2d::CurveType Polygon2d::desc()
{
	return CurveType::emPolygon;
}

bool Polygon2d::isKindOf(CurveType objType) const
{
	if (objType == Curve2d::emPolygon)
		return true;
	return Curve2d::isKindOf(objType);
}

Curve2d::CurveType Polygon2d::type() const
{
	return CurveType::emPolygon;
}

Curve2d* Polygon2d::copy() const
{
	return new Polygon2d(*this);
}

void Polygon2d::copyFrom(const Curve2d* src)
{
	*this = *(static_cast<const Polygon2d*>(src));
}

double Polygon2d::distanceTo(const Point2d& pnt) const
{
	// - 遍历每一段线段，计算最小距离
	double min = 0;
	LineSegment2d seg0;
	for (int i = 0; i < _points.size(); ++i)
	{
		const Point2d& pnt1 = _points[i];
		const Point2d& pnt2 = _points[i + 1];

		LineSegment2d seg(pnt1, pnt2);
		double dist = seg.distanceTo(pnt);
		if (i == 0 || dist < min)
		{
			min = dist;
			seg0 = seg;
		}
	}

	// - 判断最小距离的正负
	if (min == 0)
		return min;

	// -- 获取最小距离在所在直线的垂足
	Line2d line = seg0.line();
	Point2d prjPnt = line.closestPointTo(pnt);

	// -- 获取垂直向量
	Vector2d prjVec = pnt - prjPnt;

	// -- 获取直线段向内旋转90度向量
	Direction2d dir = seg0.direction();
	dir.rotateBy(CGAL_PI / 2);

	// -- 判断Direction是否一致
	if (dir.isEqualTo(prjVec.toDirection()))
	{
		min = -min;
	}

	return min;
}

Point2d Polygon2d::closestPointTo(const Point2d& pnt) const
{
	throw std::logic_error("方法未完成！");
}

void Polygon2d::push_back(Point2d pnt)
{
	_points.push_back(pnt);
}

void Polygon2d::clear()
{
	_points.clear();
}

int Polygon2d::pointSize() const
{
	return _points.size();
}

Point2d& Polygon2d::point(int n)
{
	return _points[n];
}

const Point2d& Polygon2d::point(int n) const
{
	return _points[n];
}

void Polygon2d::mergeCollinear()
{
	if (_points.size() < 3)
		return;

	std::vector<Point2d> new_points;

	int n = _points.size();
	for (int i = 0; i < n; ++i)
	{
		int prev_idx = (i == 0) ? n - 1 : i - 1;
		int curr_idx = i;
		int next_idx = (i + 1) % n;

		Point2d p1 = _points[prev_idx];
		Point2d p2 = _points[curr_idx];
		Point2d p3 = _points[next_idx];

		if (!areCollinear(p1, p2, p3))
		{
			new_points.push_back(p2);
		}
	}

	_points.clear();
	for (int i = 0; i < new_points.size(); ++i)
	{
		_points.push_back(new_points[i]);
	}
}

void Polygon2d::offset(double distance)
{
	int n = _points.size();
	if (n < 3) 
		return;  // 多边形至少需要3个点  

	std::vector<LineSegment2d> offsetSegments;

	// 第一步：偏移每个边
	for (int i = 0; i < n; ++i)
	{
		int nextIndex = (i + 1) % n;
		Point2d p1 = _points[i];
		Point2d p2 = _points[nextIndex];

		LineSegment2d seg(p1, p2);
		seg.offset(distance);
		offsetSegments.push_back(seg);
	}

	// 第二步：计算新的交点  
	std::vector<Point2d> newPoints;
	for (int i = 0; i < n; ++i)
	{
		int nextIndex = (i + 1) % n;
		LineSegment2d seg1 = offsetSegments[i];
		LineSegment2d seg2 = offsetSegments[nextIndex];

		Point2d originalIntersection = _points[nextIndex];
		Point2d intersection;
		bool hasIntersection = false;

		Line2d infiniteLine1(seg1.start(), seg1.end());
		Line2d infiniteLine2(seg2.start(), seg2.end());
		hasIntersection = infiniteLine1.intersectWith(intersection, infiniteLine2);

		if (hasIntersection)
		{
			newPoints.push_back(intersection);
		}
		else
		{
			// 如果没有交点，使用第一个段的终点  
			newPoints.push_back(seg1.end());
		}
	}

	// 第三步：更新多边形
	_points.clear();
	for (int i = 0; i < newPoints.size(); ++i)
	{
		_points.push_back(newPoints[i]);
	}
}

bool Polygon2d::unionWith(const Polygon2d& other)
{
	// 将当前多边形和其他多边形转换为 CGAL 的 Polygon_2
	Polygon_2 poly1, poly2;
	cgalUtilities::convert(*this, poly1);
	cgalUtilities::convert(other, poly2);

	// 计算两个多边形的并集
	Polygon_with_holes_2 ret;
	if(CGAL::join(poly1, poly2, ret) == false)
		return false;

	// 清空当前多边形数据
	this->clear();

	// 获取ret的外轮廓并赋值
	cgalUtilities::convert(ret, *this);

	return true;
}

bool Polygon2d::subtract(const Polygon2d& other)
{
	// 将当前多边形和其他多边形转换为 CGAL 的 Polygon_2
	Polygon_2 poly1, poly2;
	cgalUtilities::convert(*this, poly1);
	cgalUtilities::convert(other, poly2);

	// 计算两个多边形的差集
	std::vector<Polygon_with_holes_2> result;
	CGAL::difference(poly1, poly2, std::back_inserter(result));
	if (result.size() == 0)
		return false;

	// 清空当前多边形数据
	this->clear();

	// 只获取第一个的外边框
	cgalUtilities::convert(result[0], *this);

	return true;
}

Polygon2d::PointStatus Polygon2d::pointStatus(const Point2d& pnt, const MyTol& tol) const
{
	double distance = this->distanceTo(pnt);
	if (fabs(distance) < tol.equalPoint())
		return PointStatus::emOn;
	else if (distance > 0)
		return PointStatus::emOuter;
	else
		return PointStatus::emInner;
}

Point2d Polygon2d::pointInsidePolygon() const
{
	// 第一段中点向内垂直偏移50
	LineSegment2d segment(_points[0], _points[1]);
	Point2d middle = segment.midPoint();

	Direction2d dir = segment.direction();
	dir.rotateBy(CGAL_PI / 2);

	middle.transformBy(dir * 50);
	return middle;
}

void Polygon2d::transformBy(const Vector2d& offset)
{
	for (int i = 0; i < _points.size(); ++i)
	{
		_points[i].transformBy(offset);
	}
}

bool Polygon2d::areCollinear(Point2d p1, Point2d p2, Point2d p3, const MyTol& tol)
{
	// Create vectors from the points  
	Vector2d v1(p2.x - p1.x, p2.y - p1.y);
	Vector2d v2(p3.x - p2.x, p3.y - p2.y);

	// Use the cross product to determine if the vectors are parallel  
	return v1.isParallelTo(v2, tol);
}

Polygon2d& Polygon2d::operator=(const Polygon2d& src)
{
	_points = src._points;
	return *this;
}
