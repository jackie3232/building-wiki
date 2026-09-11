#include "pch.h"
#include "site.h"

#undef max
#undef min
#include "rapidjson/document.h"
#include <stdexcept>
#include "modelling.h"
#include <vector>
#include "MyUtilities.h"
#include <unordered_map>
#include "LayoutNet.h"
#include "MyOCC.hpp"
#include "MyCGAL.hpp"
#include "mystring.h"
#include "IdCreator.h"
#include "cgalUtilities.h"
#include "TopoDS_Shape_Map.h"

using namespace rapidjson;
using namespace meta_impl;
Root::Root()
	: _id(IdCreator::singleton().create())
	, _owner(nullptr)
{

}

Root::Root(const Root& src)
	: _id(src._id)
	, _name(src._name)
	, _owner(src._owner)
{

}

Root::~Root()
{

}

Root& Root::operator=(const Root& src)
{
	if (this == &src)
		return *this;

	_id = src._id;
	_name = src._name;
	_owner = src._owner;
	return *this;
}

Root::ObjectType Root::desc()
{
	return emRoot;
}

bool Root::isKindOf(ObjectType objType) const
{
	return (objType == emRoot);
}

Root* Root::copy(const Root* src)
{
	if (src == nullptr)
		return nullptr;
	return src->copy();
}

void Root::setOwner(Root* owner)
{
	_owner = owner;
}

Root* Root::owner()
{
	return _owner;
}

const Root* Root::owner() const
{
	return _owner;
}

int Root::id() const
{
	return _id;
}

void Root::setName(const char* s)
{
	_name.set(s);
}

const char* Root::name() const
{
	return _name.c_str();
}

void OpeningElement::setWidth(double width)
{
	if (width < 0.1)
		return;

	_width = width;
}

double OpeningElement::width() const
{
	return _width;
}

void OpeningElement::setHeight(double height)
{
	if (height < 0.1)
		return;

	_height = height;
}

double OpeningElement::height() const
{
	return _height;
}

OpeningElement::OpeningElement()
	: Root()
	, _width(0)
	, _height(0)
{

}

OpeningElement::OpeningElement(double width, double height)
	: Root()
	, _width(width)
	, _height(height)
{

}

OpeningElement::OpeningElement(const OpeningElement& src)
	: Root(src)
	, _width(src._width)
	, _height(src._height)
{

}

Root::ObjectType OpeningElement::desc()
{
	return Root::emOpening;
}

bool OpeningElement::isKindOf(ObjectType objType) const
{
	if (objType == Root::emOpening)
		return true;
	return Root::isKindOf(objType);
}

OpeningElement& OpeningElement::operator=(const OpeningElement& src)
{
	if (this == &src)
		return *this;

	Root::operator=(src);
	_width = src._width;
	_height = src._height;
	return *this;
}

const double DoorOpening::min_width = 1200;
const double DoorOpening::min_height = 2500;

DoorOpening::DoorOpening()
	: OpeningElement(min_width, min_height)
{
}

DoorOpening::DoorOpening(const DoorOpening& src)
	: OpeningElement(src)
{

}

DoorOpening& DoorOpening::operator=(const DoorOpening& src)
{
	if (this == &src)
		return *this;

	OpeningElement::operator=(src);
	return *this;
}

Root::ObjectType DoorOpening::desc()
{
	return Root::emDoorOpening;
}

bool DoorOpening::isKindOf(ObjectType objType) const
{
	if (objType == Root::emDoorOpening)
		return true;
	return OpeningElement::isKindOf(objType);
}

Root::ObjectType DoorOpening::type() const
{
	return Root::emDoorOpening;
}

Root* DoorOpening::copy() const
{
	DoorOpening* door = new DoorOpening(*this);
	return door;
}

void DoorOpening::copyFrom(const Root* src)
{
	*this = *static_cast<const DoorOpening*>(src);
}

WindowOpening::WindowOpening()
	: OpeningElement(1200, 1200)
{

}

WindowOpening::WindowOpening(const WindowOpening& src)
	: OpeningElement(src)
{

}

WindowOpening& WindowOpening::operator=(const WindowOpening& src)
{
	if (this == &src)
		return *this;

	OpeningElement::operator=(src);
	return *this;
}

Root::ObjectType WindowOpening::desc()
{
	return Root::emWindowOpening;
}

bool WindowOpening::isKindOf(ObjectType objType) const
{
	if (objType == Root::emWindowOpening)
		return true;
	return OpeningElement::isKindOf(objType);
}

Root::ObjectType WindowOpening::type() const
{
	return Root::emWindowOpening;
}

Root* WindowOpening::copy() const
{
	WindowOpening* window = new WindowOpening(*this);
	return window;
}

void WindowOpening::copyFrom(const Root* src)
{
	*this = *static_cast<const WindowOpening*>(src);
}

Element::Element()
	: Root()
{

}

Element::Element(const Element& src)
	: Root(src)
{

}

Element& Element::operator=(const Element& src)
{
	if (this == &src)
		return *this;

	Root::operator=(src);
	return *this;
}

Root::ObjectType Element::desc()
{
	return Root::emElement;
}

bool Element::isKindOf(ObjectType objType) const
{
	if (objType == Root::emElement)
		return true;
	return Root::isKindOf(objType);
}

const double Slab::_thickness = 300;
Slab::Slab()
	: Element()
	, _elevation(2700)
{

}

Slab::Slab(const Slab& src)
	: Element(src)
	, _profile(src._profile)
	, _elevation(src._elevation)
{

}

Slab& Slab::operator=(const Slab& src)
{
	if (this == &src)
		return *this;

	Element::operator=(src);
	_profile = src._profile;
	_elevation = src._elevation;
	return *this;
}

Root::ObjectType Slab::desc()
{
	return Root::emSlab;
}

bool Slab::isKindOf(ObjectType objType) const
{
	if (objType == Root::emSlab)
		return true;
	return Element::isKindOf(objType);
}

Root::ObjectType Slab::type() const
{
	return Root::emSlab;
}

Root* Slab::copy() const
{
	Slab* slab = new Slab(*this);
	return slab;
}

void Slab::copyFrom(const Root* src)
{
	*this = *static_cast<const Slab*>(src);
}

void Slab::setProfile(const Polygon2d& profile)
{
	_profile = profile;
}

const Polygon2d& Slab::profile() const
{
	return _profile;
}

double Slab::thickness()
{
	return _thickness;
}

void Slab::setElevation(double elevation)
{
	_elevation = elevation;
}

double Slab::elevation() const
{
	return _elevation;
}

Point2d Slab::positionId() const
{
	return _profile.pointInsidePolygon();
}

bool Slab::modelling(Body& body) const
{
	Polygon2d profile = _profile;

	// 重定位原点
	Point2d origin = profile.pointInsidePolygon();
	Vector2d offset = Point2d(0, 0) - origin;
	profile.transformBy(offset);

	// 创建在XOY平面往上拉伸的板（不考虑elevation）
	if (Modelling::extrude(body, profile, _thickness) == false)
		return false;

	// 构造转换矩阵
	Matrix3d mat;
	mat.origin = Point(origin.x, origin.y, _elevation);
	body.transformBy(mat);

	return true;
}

bool Slab::_addOpening(Body& body) const
{
	throw std::logic_error("方法未完成！");
}

const double Wall::thickness = 300;
Root::ObjectType Wall::desc()
{
	return Root::emWall;
}

bool Wall::isKindOf(ObjectType objType) const
{
	if (objType == Root::emWall)
		return true;
	return Element::isKindOf(objType);
}

Wall::Wall()
	: Element()
	, _elevation(0)
	, _height(3000)
	, _connectionType(emNormal)
	, _opening(nullptr)
{

}

Wall::Wall(const Wall& src)
	: Element(src)
	, _elevation(src._elevation)
	, _height(src._height)
	, _connectionType(src._connectionType)
	, _opening(static_cast<OpeningElement*>(OpeningElement::copy(src._opening)))
{

}

Wall& Wall::operator=(const Wall& src)
{
	if (this == &src)
		return *this;

	Element::operator=(src);
	_elevation = src._elevation;
	_height = src._height;
	_connectionType = src._connectionType;
	
	delete _opening;
	_opening = static_cast<OpeningElement*>(OpeningElement::copy(src._opening));

	return *this;
}

Wall::~Wall()
{
	delete _opening;
}

void Wall::setElevation(double elevation)
{
	_elevation = elevation;
}

double Wall::elevation() const
{
	return _elevation;
}

void Wall::setHeight(double height)
{
	_height = height;
}

double Wall::height() const
{
	return _height;
}

void Wall::setConnectionType(ConnectionType type)
{
	_connectionType = type;

	delete _opening;
	_opening = nullptr;

	switch (_connectionType)
	{
	case emNormal:
		break;
	case emUnion:
		break;
	case emDoor:
	{
		_opening = new DoorOpening();
	}
		break;
	case emWindow:
	{
		_opening = new WindowOpening();
	}
		break;
	default:
		break;
	}
}

Wall::ConnectionType Wall::connectionType() const
{
	return _connectionType;
}

OpeningElement* Wall::opening() const
{
	return _opening;
}

Space* Wall::space1()
{
	Storey* storey = static_cast<Storey*>(this->owner());

	Edge edge;
	if (storey->findEdge(edge, this->id()) == false)
		return nullptr;

	Face face = edge.face1();
	return storey->findSpace(face);
}

const Space* Wall::space1() const
{
	const Storey* storey = static_cast<const Storey*>(this->owner());

	Edge edge;
	if (storey->findEdge(edge, this->id()) == false)
		return nullptr;

	Face face = edge.face1();
	return storey->findSpace(face);
}

Space* Wall::space2()
{
	Storey* storey = static_cast<Storey*>(this->owner());

	Edge edge;
	if (storey->findEdge(edge, this->id()) == false)
		return nullptr;

	Face face = edge.face2();
	return storey->findSpace(face);
}

const Space* Wall::space2() const
{
	const Storey* storey = static_cast<const Storey*>(this->owner());

	Edge edge;
	if (storey->findEdge(edge, this->id()) == false)
		return nullptr;

	Face face = edge.face2();
	return storey->findSpace(face);
}

bool Wall::modelling(Body& body) const
{
	if (_opening != nullptr)
		return _addOpening(body);
	return true;
}

LinearWall::LinearWall()
	: Wall()
	, _axis()
{

}

LinearWall::LinearWall(const LinearWall& src)
	: Wall(src)
	, _axis(src._axis)
{

}

LinearWall::LinearWall(const LineSegment2d& axis)
	: Wall()
	, _axis(axis)
{

}

Root::ObjectType LinearWall::desc()
{
	return Root::emLinearWall;
}

bool LinearWall::isKindOf(ObjectType objType) const
{
	if (objType == Root::emLinearWall)
		return true;
	return Wall::isKindOf(objType);
}

Root::ObjectType LinearWall::type() const
{
	return Root::emLinearWall;
}

Root* LinearWall::copy() const
{
	LinearWall* wall = new LinearWall(*this);
	return wall;
}

void LinearWall::copyFrom(const Root* src)
{
	*this = *static_cast<const LinearWall*>(src);
}

void LinearWall::setAxis(const Segment2d* axis)
{
	_axis = *static_cast<const LineSegment2d*>(axis);
}

LineSegment2d& LinearWall::axis()
{
	return _axis;
}

const LineSegment2d& LinearWall::axis() const
{
	return _axis;
}

bool LinearWall::modelling(Body& body) const
{
	// 获取直线段
	LineSegment2d seg = _axis;

	// 延伸两端
	seg.extendFromStart(thickness / 2);
	seg.extendFromEnd(thickness / 2);

	// 创建UCS下轮廓多边形
	double length = seg.length();
	Polygon2d profile;
	MyUtilities::createProfile(profile, length, thickness);

	// 挤出UCS下的几何体
	if (Modelling::extrude(body, profile, _height) == false)
		return false;

	// 转换到WCS下
	Matrix3d mat;

	// - 计算原点
	Point2d pnt = positionId();
	mat.origin.set(pnt.x, pnt.y, _elevation);

	// - 计算x轴
	Direction2d xaxis_ = seg.direction();
	mat.xaxis.set(xaxis_.x, xaxis_.y, 0);

	// - z轴为默认，向上；计算y轴
	mat.yaxis = mat.xaxis.crossProduct(mat.zaxis);

	// - 转换
	body.transformBy(mat);

	return Wall::modelling(body);
}

bool LinearWall::is_vertical() const
{
	if (_axis.vector().isParallelTo(Vector2d(0, 1)))
		return true;

	return false;
}

bool LinearWall::is_horizontal() const
{
	if (_axis.vector().isParallelTo(Vector2d(1, 0)))
		return true;

	return false;
}

LinearWall& LinearWall::operator=(const LinearWall& src)
{
	if (this == &src)
		return *this;

	Wall::operator =(src);
	_axis = src._axis;
	return *this;
}

bool LinearWall::_addOpening(Body& body) const
{
	switch (_opening->type())
	{
	case emDoorOpening:
	{
		return _addDoor(body, _opening->width(), _opening->height());
	}
		break;
	case emWindowOpening:
	{
		return _addWindow(body, _opening->width(), _opening->height());
	}
		break;
	default:
		break;
	}

	return false;
}

bool LinearWall::_addDoor(Body& body, double width, double height, double offset) const
{
	double length = _axis.length();
	if (width > length)
		width = length;

	if (height > _height)
		height = _height;

	// 暂不处理offset
	// TODO...

	// - 创建布尔减工具
	// -- 创建轮廓
	LineSegment2d seg = _axis;
	seg.resetBasedOnMiddle(width);

	Polygon2d profile;
	MyUtilities::createProfile(profile, seg, thickness);

	// -- 挤出几何体
	Body tool;
	if (Modelling::extrude(tool, profile, height, _elevation) == false)
		return false;

	// -- 进行布尔运算减
	body = body - tool;
	return true;
}

bool LinearWall::_addWindow(Body& body, double width, double height, double offset) const
{
	double length = _axis.length();
	if (width > length)
		width = length;

	if (height > _height)
		height = _height;

	// 暂不处理offset
	// TODO...

	// - 创建布尔减工具
	// -- 创建轮廓
	LineSegment2d seg = _axis;
	seg.resetBasedOnMiddle(width);

	Polygon2d profile;
	MyUtilities::createProfile(profile, seg, thickness);

	// -- 计算窗户高度在中间时需要增加的高度
	double sub_elevation = (_height - height) / 2;

	// -- 挤出几何体
	Body tool;
	if (Modelling::extrude(tool, profile, height, _elevation + sub_elevation) == false)
		return false;

	// -- 进行布尔运算减
	body = body - tool;
	return true;
}

Point2d LinearWall::positionId() const
{
	return _axis.midPoint();
}

CircularWall::CircularWall()
	: Wall()
	, _axis()
{

}

CircularWall::CircularWall(const CircularWall& src)
	: Wall(src)
	, _axis(src._axis)
{

}

CircularWall::CircularWall(const CircArc2d& axis)
	: Wall()
	, _axis(axis)
{

}

Root::ObjectType CircularWall::desc()
{
	return Root::emCircularWall;
}

bool CircularWall::isKindOf(ObjectType objType) const
{
	if (objType == Root::emCircularWall)
		return true;
	return Wall::isKindOf(objType);
}

Root::ObjectType CircularWall::type() const
{
	return Root::emCircularWall;
}

Root* CircularWall::copy() const
{
	CircularWall* wall = new CircularWall(*this);
	return wall;
}

void CircularWall::copyFrom(const Root* src)
{
	*this = *static_cast<const CircularWall*>(src);
}

void CircularWall::setAxis(const Segment2d* axis)
{
	_axis = *static_cast<const CircArc2d*>(axis);
}

bool CircularWall::modelling(Body& body) const
{
	throw std::logic_error("方法未完成！");
}

CircularWall& CircularWall::operator=(const CircularWall& src)
{
	if (this == &src)
		return *this;

	Wall::operator =(src);
	_axis = src._axis;
	return *this;
}

bool CircularWall::_addOpening(Body& body) const
{
	throw std::logic_error("方法未完成！");
}

Point2d CircularWall::positionId() const
{
	return _axis.midPoint();
}

class Walls::Impl
{
public:
	void clear()
	{
		_walls.clear();
		_wallId_wallIndex_map.clear();
		_edgeId_wallId_map.clear();
		_wallId_edgeId_map.clear();
	}

	int push_back(const LinearWall& wall)
	{
		_walls.push_back(wall);
		int index = int(_walls.size() - 1);
		_wallId_wallIndex_map.insert(std::make_pair(wall.id(), index));
		return index;
	}

	void insert(int edgeId, int index)
	{
		_edgeId_wallId_map.insert(std::make_pair(edgeId, _walls[index].id()));
		_wallId_edgeId_map.insert(std::make_pair(_walls[index].id(), edgeId));
	}

	int size() const
	{
		return (int)_walls.size();
	}

	LinearWall* get(int wallId)
	{
		std::unordered_map<int, int>::iterator it = _wallId_wallIndex_map.find(wallId);
		if (it == _wallId_wallIndex_map.end())
			return nullptr;

		return &_walls[it->second];
	}

	const LinearWall* get(int wallId) const
	{
		std::unordered_map<int, int>::const_iterator it = _wallId_wallIndex_map.find(wallId);
		if (it == _wallId_wallIndex_map.end())
			return nullptr;

		return &_walls[it->second];
	}

	LinearWall* findFromEdge(const Edge& edge)
	{
		std::unordered_map<int, int>::iterator it = _edgeId_wallId_map.find(edge.id());
		if (it == _edgeId_wallId_map.end())
		{
			it = _edgeId_wallId_map.find(edge.oppsite().id());
			if (it == _edgeId_wallId_map.end())
				return nullptr;
		}

		std::unordered_map<int, int>::iterator it1 = _wallId_wallIndex_map.find(it->second);
		if (it1 == _wallId_wallIndex_map.end())
			return nullptr;

		return &_walls[it1->second];
	}

	const LinearWall* findFromEdge(const Edge& edge) const
	{
		std::unordered_map<int, int>::const_iterator it = _edgeId_wallId_map.find(edge.id());
		if (it == _edgeId_wallId_map.end())
		{
			it = _edgeId_wallId_map.find(edge.oppsite().id());
			if (it == _edgeId_wallId_map.end())
				return nullptr;
		}

		std::unordered_map<int, int>::const_iterator it1 = _wallId_wallIndex_map.find(it->second);
		if (it1 == _wallId_wallIndex_map.end())
			return nullptr;

		return &_walls[it1->second];
	}

	bool findEdge(int& edgeId, int wallId)
	{
		std::unordered_map<int, int>::iterator it = _wallId_edgeId_map.find(wallId);
		if (it == _wallId_edgeId_map.end())
			return false;

		edgeId = it->second;
		return true;
	}

	const bool findEdge(int& edgeId, int wallId) const
	{
		std::unordered_map<int, int>::const_iterator it = _wallId_edgeId_map.find(wallId);
		if (it == _wallId_edgeId_map.end())
			return false;

		edgeId = it->second;
		return true;
	}

	LinearWall& operator[](int n)
	{
		return _walls[n];
	}

	const LinearWall& operator[](int n) const
	{
		return _walls[n];
	}

private:
	std::vector<LinearWall> _walls;
	std::unordered_map<int, int> _wallId_wallIndex_map;
	std::unordered_map<int, int> _edgeId_wallId_map;
	std::unordered_map<int, int> _wallId_edgeId_map;
};

Walls::Walls()
	: _impl(new Impl())
{

}

Walls::Walls(const Walls& src)
	: _impl(new Impl(*src._impl))
{

}

Walls::~Walls()
{
	delete _impl;
}

int Walls::push_back(const LinearWall& wall)
{
	return _impl->push_back(wall);
}

void Walls::clear()
{
	_impl->clear();
}

int Walls::size() const
{
	return _impl->size();
}

void Walls::insert(const Edge& edge, int index)
{
	_impl->insert(edge.id(), index);
}

LinearWall* Walls::find(const Edge& edge)
{
	return _impl->findFromEdge(edge);
}

const LinearWall* Walls::find(const Edge& edge) const
{
	return _impl->findFromEdge(edge);
}

LinearWall* Walls::get(int wallId)
{
	return _impl->get(wallId);
}

const LinearWall* Walls::get(int wallId) const
{
	return _impl->get(wallId);
}

bool Walls::findEdge(int& edgeId, int wallId)
{
	return _impl->findEdge(edgeId, wallId);
}

bool Walls::findEdge(int& edgeId, int wallId) const
{
	return _impl->findEdge(edgeId, wallId);
}

Walls& Walls::operator=(const Walls& src)
{
	*_impl = *src._impl;
	return *this;
}

LinearWall& Walls::operator[](int n)
{
	return (*_impl)[n];
}

const LinearWall& Walls::operator[](int n) const
{
	return (*_impl)[n];
}

class ObjectPtrs::Impl
{
public:
	void clear()
	{
		_walls.clear();
	}

	void push_back(Root* wall)
	{
		_walls.push_back(wall);
	}

	void insert_at_begin(Root* wall)
	{
		_walls.insert(_walls.begin(), wall);
	}

	int size() const
	{
		return (int)_walls.size();
	}

	Root* operator[](int n)
	{
		return _walls[n];
	}

	const Root* operator[](int n) const
	{
		return _walls[n];
	}

private:
	std::vector<Root*> _walls;
};

ObjectPtrs::ObjectPtrs()
	: _impl(new Impl())
{

}

ObjectPtrs::ObjectPtrs(const ObjectPtrs& src)
	: _impl(new Impl(*src._impl))
{

}

ObjectPtrs::~ObjectPtrs()
{
	delete _impl;
}

void ObjectPtrs::push_back(Root* wall)
{
	_impl->push_back(wall);
}

void ObjectPtrs::insert_at_begin(Root* wall)
{
	_impl->insert_at_begin(wall);
}

void ObjectPtrs::clear()
{
	_impl->clear();
}

int ObjectPtrs::size() const
{
	return _impl->size();
}

ObjectPtrs* ObjectPtrs::copy() const
{
	return new ObjectPtrs(*this);
}

ObjectPtrs& ObjectPtrs::operator=(const ObjectPtrs& src)
{
	*_impl = *src._impl;
	return *this;
}

WallPtrs::WallPtrs()
	: ObjectPtrs()
{

}

WallPtrs::WallPtrs(const WallPtrs& src)
	: ObjectPtrs(src)
{

}

WallPtrs::~WallPtrs()
{

}

void WallPtrs::push_back(LinearWall* wall)
{
	ObjectPtrs::push_back(wall);
}

void WallPtrs::insert_at_begin(LinearWall* wall)
{
	ObjectPtrs::insert_at_begin(wall);
}

LinearWall* WallPtrs::find(const Point2d& position)
{
	for (int i = 0; i < _impl->size(); ++i)
	{
		LinearWall* wall = (LinearWall*)(*_impl)[i];
		if (wall->positionId().isEqualTo(position))
			return wall;
	}

	return nullptr;
}

const LinearWall* WallPtrs::find(const Point2d& position) const
{
	for (int i = 0; i < _impl->size(); ++i)
	{
		const LinearWall* wall = (LinearWall*)(*_impl)[i];
		if (wall->positionId().isEqualTo(position))
			return wall;
	}

	return nullptr;
}

LinearWall* WallPtrs::operator[](int n)
{
	return (LinearWall*)(*_impl)[n];
}

const LinearWall* WallPtrs::operator[](int n) const
{
	return (LinearWall*)(*_impl)[n];
}

WallPtrs& WallPtrs::operator=(const WallPtrs& src)
{
	ObjectPtrs::operator=(src);
	return *this;
}


SpacePtrs::SpacePtrs()
	: ObjectPtrs()
{

}

SpacePtrs::SpacePtrs(const SpacePtrs& src)
	: ObjectPtrs(src)
{

}

SpacePtrs::~SpacePtrs()
{

}

void SpacePtrs::push_back(Space* wall)
{
	ObjectPtrs::push_back(wall);
}

void SpacePtrs::insert_at_begin(Space* wall)
{
	ObjectPtrs::insert_at_begin(wall);
}

Space* SpacePtrs::operator[](int n)
{
	return (Space*)(*_impl)[n];
}

const Space* SpacePtrs::operator[](int n) const
{
	return (Space*)(*_impl)[n];
}

SpacePtrs& SpacePtrs::operator=(const SpacePtrs& src)
{
	ObjectPtrs::operator=(src);
	return *this;
}

SpatialElement::SpatialElement()
	: Root()
{

}

SpatialElement::SpatialElement(const SpatialElement& src)
	: Root(src)
	, _footprint(src._footprint)
{

}

SpatialElement& SpatialElement::operator=(const SpatialElement& src)
{
	if (this == &src)
		return *this;

	Root::operator=(src);
	_footprint = src._footprint;
	return *this;
}

Root::ObjectType SpatialElement::desc()
{
	return Root::emSpatialElement;
}

bool SpatialElement::isKindOf(ObjectType objType) const
{
	if (objType == Root::emSpatialElement)
		return true;
	return Root::isKindOf(objType);
}

void SpatialElement::setFootprint(const Polygon2d& footprint)
{
	_footprint = footprint;
}

Polygon2d& SpatialElement::footprint()
{
	return _footprint;
}

const Polygon2d& SpatialElement::footprint() const
{
	return _footprint;
}

Space::Space()
	: SpatialElement()
	, _spaceType(emInnerSpace)
	, _is_unbounded(false)
	, _face_id(0)
	, _height(3000)
	, _elevation(0)
{

}

Space::Space(const Space& src)
	: SpatialElement(src)
	, _spaceType(src._spaceType)
	, _is_unbounded(src._is_unbounded)
	, _floor(src._floor)
	, _roof(src._roof)
	, _face_id(src._face_id)
	, _height(src._height)
	, _elevation(src._elevation)
{

}

Space::~Space()
{

}

Root::ObjectType Space::desc()
{
	return Root::emSpace;
}

bool Space::isKindOf(ObjectType objType) const
{
	if (objType == Root::emSpace)
		return true;
	return SpatialElement::isKindOf(objType);
}

Root::ObjectType Space::type() const
{
	return Root::emSpace;
}

void meta_impl::Space::setName(const char* s)
{
	Root::setName(s);
	_match_space_type();

	_roof.setName(MyUtilities::combin(_name.c_str(), std::string("roof")).c_str());
	_floor.setName(MyUtilities::combin(_name.c_str(), std::string("floor")).c_str());
}

Root* Space::copy() const
{
	return new Space(*this);
}

void Space::copyFrom(const Root* src)
{
	*this = *(static_cast<const Space*>(src));
}

void Space::setSpaceType(SpaceType type)
{
	_spaceType = type;
}

Space::SpaceType Space::spaceType() const
{
	return _spaceType;
}

const char* Space::spaceTypeName(SpaceType type)
{
	switch (type)
	{
	case emInnerSpace:
		return "室内";
	case emBalcony:
		return "阳台";
	case emCourtyard:
		return "庭院";
	case emOuterSpace:
		return "外部";
	default:
		return nullptr;
	}
}

void Space::setFootprint(const Polygon2d& footprint)
{
	SpatialElement::setFootprint(footprint);

	Polygon2d outerloop = _footprint;
	outerloop.offset(Wall::thickness / 2);
	outerloop.mergeCollinear();

	_floor.setProfile(outerloop);
	_roof.setProfile(outerloop);
}

void Space::setIsUnbounded(bool unbounded)
{
	_is_unbounded = unbounded;
	setName("外部空间");
	_spaceType = emOuterSpace;
}

bool Space::isUnbounded() const
{
	return _is_unbounded;
}

void Space::setHeight(double height)
{
	_height = height;
}

double Space::height() const
{
	return _height;
}

void Space::setElevation(double elevation)
{
	_elevation = elevation;
	_floor.setElevation(_elevation);
	_roof.setElevation(elevation + _height - _roof.thickness());
}

double Space::elevation() const
{
	return _elevation;
}

Slab& Space::floor()
{
	return _floor;
}

const Slab& Space::floor() const
{
	return _floor;
}

Slab& Space::roof()
{
	return _roof;
}

const Slab& Space::roof() const
{
	return _roof;
}

Space& Space::operator=(const Space& src)
{
	if (this == &src)
		return *this;

	SpatialElement::operator=(src);
	_spaceType = src._spaceType;
	_is_unbounded = src._is_unbounded;
	_floor = src._floor;
	_roof = src._roof;
	_face_id = src._face_id;
	_height = src._height;
	_elevation = src._elevation;
	return *this;
}

bool Space::modelling(Body& shape) const
{
	shape.setName(_name.c_str());
	return Modelling::extrude(shape, _footprint, _elevation + _height);
}

bool Space::footprint_modelling(Body& face) const
{
	face.setName(_name.c_str());
	return Modelling::createFace(face, _footprint);
}

bool Space::drawName(Body& txt) const
{
	return false;
}

void meta_impl::Space::_match_space_type()
{
	if (_name.contains("阳台"))
		_spaceType = emBalcony;
	else if (_name.contains("院"))
		_spaceType = emCourtyard;
	else
		_spaceType = emInnerSpace;
}

class Spaces::Impl
{
public:
	void clear()
	{
		_spaces.clear();
		_name_index_map.clear();
		_spaceId_spaceIndex_map.clear();
		_faceId_spaceId_map.clear();
		_spaceId_faceId_map.clear();
	}

	int push_back(const Space& space)
	{
		_spaces.push_back(space);
		int index = int(_spaces.size() - 1);
		_spaceId_spaceIndex_map.insert(std::make_pair(space.id(), index));
		_name_index_map.insert(std::make_pair(space.name(), index));
		return index;
	}

	void insert(int faceId, int spaceIndex)
	{
		_faceId_spaceId_map.insert(std::make_pair(faceId, _spaces[spaceIndex].id()));
		_spaceId_faceId_map.insert(std::make_pair(_spaces[spaceIndex].id(), faceId));
	}

	Space* get(const char* name)
	{
		std::unordered_map<std::string, int>::iterator it = _name_index_map.find(name);
		if (it == _name_index_map.end())
			return nullptr;

		return &_spaces[it->second];
	}

	const Space* get(const char* name) const
	{
		std::unordered_map<std::string, int>::const_iterator it = _name_index_map.find(name);
		if (it == _name_index_map.end())
			return nullptr;

		return &_spaces[it->second];
	}

	Space* get(int spaceId)
	{
		std::unordered_map<int, int>::iterator it = _spaceId_spaceIndex_map.find(spaceId);
		if (it == _spaceId_spaceIndex_map.end())
			return nullptr;

		return &_spaces[it->second];
	}

	const Space* get(int spaceId) const
	{
		std::unordered_map<int, int>::const_iterator it = _spaceId_spaceIndex_map.find(spaceId);
		if (it == _spaceId_spaceIndex_map.end())
			return nullptr;

		return &_spaces[it->second];
	}

	Space* findFromFace(int faceId)
	{
		std::unordered_map<int, int>::iterator it = _faceId_spaceId_map.find(faceId);
		if (it == _faceId_spaceId_map.end())
			return nullptr;

		std::unordered_map<int, int>::iterator it1 = _spaceId_spaceIndex_map.find(it->second);
		if (it1 == _spaceId_spaceIndex_map.end())
			return nullptr;

		return &_spaces[it1->second];
	}

	const Space* findFromFace(int faceId) const
	{
		std::unordered_map<int, int>::const_iterator it = _faceId_spaceId_map.find(faceId);
		if (it == _faceId_spaceId_map.end())
			return nullptr;

		std::unordered_map<int, int>::const_iterator it1 = _spaceId_spaceIndex_map.find(it->second);
		if (it1 == _spaceId_spaceIndex_map.end())
			return nullptr;

		return &_spaces[it1->second];
	}

	bool findFace(int& faceId, int spaceId)
	{
		std::unordered_map<int, int>::iterator it = _spaceId_faceId_map.find(spaceId);
		if (it == _spaceId_faceId_map.end())
			return false;

		faceId = it->second;
		return true;
	}

	const bool findFace(int& faceId, int spaceId) const
	{
		std::unordered_map<int, int>::const_iterator it = _spaceId_faceId_map.find(spaceId);
		if (it == _spaceId_faceId_map.end())
			return false;

		faceId = it->second;
		return true;
	}

	int size() const
	{
		return (int)_spaces.size();
	}

	Space& operator[](int n)
	{
		return _spaces[n];
	}

	const Space& operator[](int n) const
	{
		return _spaces[n];
	}

private:
	std::vector<Space> _spaces;
	std::unordered_map<std::string, int> _name_index_map;
	std::unordered_map<int, int> _spaceId_spaceIndex_map;
	std::unordered_map<int, int> _faceId_spaceId_map;
	std::unordered_map<int, int> _spaceId_faceId_map;
};

Spaces::Spaces()
	: _impl(new Impl())
{

}

Spaces::Spaces(const Spaces& src)
	: _impl(new Impl(*src._impl))
{

}

Spaces::~Spaces()
{
	delete _impl;
}

int Spaces::push_back(const Space& space)
{
	return _impl->push_back(space);
}

void Spaces::clear()
{
	_impl->clear();
}

int Spaces::size() const
{
	return _impl->size();
}

void Spaces::insert(int faceId, int spaceIndex)
{
	_impl->insert(faceId, spaceIndex);
}

Space* Spaces::get(const char* name)
{
	return _impl->get(name);
}

const Space* Spaces::get(const char* name) const
{
	return _impl->get(name);
}

Space* Spaces::get(int id)
{
	return _impl->get(id);
}

const Space* Spaces::get(int id) const
{
	return _impl->get(id);
}

Space* Spaces::findFromFace(int faceId)
{
	return _impl->findFromFace(faceId);
}

const Space* Spaces::findFromFace(int faceId) const
{
	return _impl->findFromFace(faceId);
}

bool Spaces::findFace(int& faceId, int spaceId)
{
	return _impl->findFace(faceId, spaceId);
}

bool Spaces::findFace(int& faceId, int spaceId) const
{
	return _impl->findFace(faceId, spaceId);
}

Spaces& Spaces::operator=(const Spaces& src)
{
	*_impl = *src._impl;
	return *this;
}

Space& Spaces::operator[](int n)
{
	return (*_impl)[n];
}

const Space& Spaces::operator[](int n) const
{
	return (*_impl)[n];
}

Storey::Storey()
	: SpatialElement()
	, _height(3000)
	, _elevation(0)
	, _layoutNet(new LayoutNet())
{

}

Storey::Storey(const Storey& src)
	: SpatialElement(src)
	, _height(src._height)
	, _elevation(src._elevation)
	, _layoutNet(new LayoutNet(*src._layoutNet))
	, _spaces(src._spaces)
	, _walls(src._walls)
{

}

Storey::~Storey()
{
	delete _layoutNet;
}

Root::ObjectType Storey::desc()
{
	return Root::emStorey;
}

bool Storey::isKindOf(ObjectType objType) const
{
	if (objType == Root::emStorey)
		return true;
	return SpatialElement::isKindOf(objType);
}

Root::ObjectType Storey::type() const
{
	return Root::emStorey;
}

Root* Storey::copy() const
{
	return new Storey(*this);
}

void Storey::copyFrom(const Root* src)
{
	*this = *(static_cast<const Storey*>(src));
}

void Storey::setHeight(double height)
{
	_height = height;
}

double Storey::height() const
{
	return _height;
}

void Storey::setElevation(double elevation)
{
	_elevation = elevation;
}

double Storey::elevation() const
{
	return _elevation;
}

Space& Storey::addSpace(const Space& space)
{
	int index = _spaces.push_back(space);
	Space& space_ = _spaces[index];
	space_.setOwner(this);
	return space_;
}

int Storey::spaceSize() const
{
	return (int)_spaces.size();
}

Space& Storey::space(int n)
{
	return _spaces[n];
}

const Space& Storey::space(int n) const
{
	return _spaces[n];
}

Space* Storey::getSpace(int spaceId)
{
	return _spaces.get(spaceId);
}

const Space* Storey::getSpace(int spaceId) const
{
	return _spaces.get(spaceId);
}

Space* Storey::findSpace(const Face& face)
{
	return _spaces.findFromFace(face.id());
}

const Space* Storey::findSpace(const Face& face) const
{
	return _spaces.findFromFace(face.id());
}

bool Storey::findFace(int& faceId, int spaceId)
{
	return _spaces.findFace(faceId, spaceId);
}

bool Storey::findFace(int& faceId, int spaceId) const
{
	return _spaces.findFace(faceId, spaceId);
}

bool Storey::findFace(Face& face, int spaceId) const
{
	int faceId = 0;
	if (findFace(faceId, spaceId) == false)
		return false;

	 face = _layoutNet->getFace(faceId);
	 return !face.isNull();
}

void Storey::refreshLayoutNet()
{
	_layoutNet->clear();

	// 生成layoutNet
	for (int i = 0; i < _spaces.size(); ++i)
	{
		const Space& space = _spaces[i];
		_layoutNet->insert(space.footprint());
	}

	// 添加连接关系
	for (int i = 0; i < _spaces.size(); ++i)
	{
		// - 查找Face
		const Space& space = _spaces[i];
		Topology* topology = _layoutNet->find(space.footprint().pointInsidePolygon());

		// - 建立关联
		if (topology != nullptr && topology->type() == Topology::emFace)
		{
			Face* face = static_cast<Face*>(topology);
			_spaces.insert(face->id(), i);
		}
	}

	// 添加unbounded face
	Space unbounded;
	unbounded.setIsUnbounded(true);
	int index = _spaces.push_back(unbounded);

	Face unbounded_face = _layoutNet->unboundedFace();
	_spaces.insert(unbounded_face.id(), index);

	_layoutNet->refresh_idmap();
}

int Storey::createWalls()
{
	_walls.clear();

	// 创建墙
	int n = 1;
	for (auto edgeIt = _layoutNet->edgeBegin(); edgeIt != _layoutNet->edgeEnd(); ++edgeIt)
	{
		Edge edge = *edgeIt;
		LineSegment2d segment = edge.curve();

		LinearWall wall(segment);
		wall.setName(MyUtilities::combine("IfcWall", n++).c_str());
		wall.setElevation(_elevation);
		wall.setOwner(this);

		double height = 0;
		if (isBalconyWall(edge))
			height = 1500;
		else
			height = _height;
		wall.setHeight(height);

		int n = _walls.push_back(wall);
		_walls.insert(edge, n);
	}

	return _walls.size();
}

int Storey::wallSize() const
{
	return _walls.size();
}

LinearWall& Storey::wall(int n)
{
	return _walls[n];
}

const LinearWall& Storey::wall(int n) const
{
	return _walls[n];
}

LinearWall* Storey::getWall(int wallId)
{
	return _walls.get(wallId);
}

const LinearWall* Storey::getWall(int wallId) const
{
	return _walls.get(wallId);
}

bool Storey::findEdge(Edge& edge, int wallId)
{
	int edgeId = 0;
	if (_walls.findEdge(edgeId, wallId) == false)
		return false;

	edge = _layoutNet->getHalfedge(edgeId).edge();
	return true;
}

bool Storey::findEdge(Edge& edge, int wallId) const
{
	int edgeId = 0;
	if (_walls.findEdge(edgeId, wallId) == false)
		return false;

	edge = _layoutNet->getHalfedge(edgeId).edge();
	return true;
}

bool Storey::findSpaces(Space*& space1, Space*& space2, const LinearWall& wall)
{
	int edgeId = 0;
	if (_walls.findEdge(edgeId, wall.id()) == false)
		return false;

	Halfedge he = _layoutNet->getHalfedge(edgeId);
	Face face1 = he.face();
	Face face2 = he.twin().face();

	space1 = _spaces.findFromFace(face1.id());
	space2 = _spaces.findFromFace(face2.id());

	if (space1 == nullptr || space2 == nullptr)
		return false;
	return true;
}

bool Storey::findSpaces(Space*& space1, Space*& space2, const Edge& wallAxis)
{
	Face face1 = wallAxis.face1();
	Face face2 = wallAxis.face2();

	space1 = _spaces.findFromFace(face1.id());
	space2 = _spaces.findFromFace(face2.id());

	if (space1 == nullptr || space2 == nullptr)
		return false;
	return true;
}

bool Storey::isBalconyWall(const LinearWall& wall)
{
	Space *space1 = nullptr, *space2 = nullptr;
	if (findSpaces(space1, space2, wall) == false)
		return false;

	if (space1->isUnbounded())
	{
		MyString s = space2->name();
		if (s.contains("阳台"))
			return true;
	}
	else if (space2->isUnbounded())
	{
		MyString s = space1->name();
		if (s.contains("阳台"))
			return true;
	}

	return false;
}

bool Storey::isBalconyWall(const Edge& wallAxis)
{
	Space* space1 = nullptr, * space2 = nullptr;
	if (findSpaces(space1, space2, wallAxis) == false)
		return false;

	if (space1->isUnbounded())
	{
		MyString s = space2->name();
		if (s.contains("阳台"))
			return true;
	}
	else if (space2->isUnbounded())
	{
		MyString s = space1->name();
		if (s.contains("阳台"))
			return true;
	}

	return false;
}

Element* Storey::find(const Point2d& position)
{
	Topology* topology = _layoutNet->find(position);
	if (topology == nullptr)
		return nullptr;

	Element* element = nullptr;
	switch (topology->type())
	{
	case Topology::emEdge:
	{
		Edge* edge = static_cast<Edge*>(topology);
		element = _walls.find(*edge);
	}
		break;
	case Topology::emFace:
	{
		Face* face = static_cast<Face*>(topology);
		Space* space = _spaces.findFromFace(face->id());
		if (space != nullptr)
		{
			return &space->floor();
		}
	}
		break;
	default:
		break;
	}
	delete topology;

	return element;
}

const Element* Storey::find(const Point2d& position) const
{
	Topology* topology = _layoutNet->find(position);
	if (topology == nullptr)
		return nullptr;

	const Element* element = nullptr;
	switch (topology->type())
	{
	case Topology::emEdge:
	{
		Edge* edge = static_cast<Edge*>(topology);
		element = _walls.find(*edge);
	}
	break;
	case Topology::emFace:
	{
		Face* face = static_cast<Face*>(topology);
		const Space* space = _spaces.findFromFace(face->id());
		if (space != nullptr)
		{
			return &space->floor();
		}
	}
	break;
	default:
		break;
	}
	delete topology;

	return element;
}

Element* Storey::find(int topologyId)
{
	Topology* topology = _layoutNet->get(topologyId);
	if (topology == nullptr)
		return nullptr;

	Element* element = nullptr;
	switch (topology->type())
	{
	case Topology::emHalfedge:
	{
		element = _walls.find(*static_cast<Edge*>(topology));
	}
		break;
	case Topology::emFace:
	{
		Space* space = _spaces.findFromFace(topology->id());
		if (space != nullptr)
		{
			element = &space->floor();
		}
	}
		break;
	default:
		break;
	}
	delete topology;

	return element;
}

bool Storey::addConnection(const char* spaceName1, const char* spaceName2,
	Wall::ConnectionType type, double width, double height, Position wallPosition, int number)
{
	Space* space1 = _spaces.get(spaceName1);
	Space* space2 = _spaces.get(spaceName2);
	if (space1 == nullptr || space2 == nullptr)
		return false;

	WallPtrs walls;
	if (findConnections(walls, space1->id(), space2->id()) == false)
		return false;

	if (type == Wall::emUnion)
	{
		for (int i = 0; i < walls.size(); ++i)
		{
			walls[i]->setConnectionType(type);
		}

		return true;
	}

	Wall* targetWall = nullptr;
	if (walls.size() == 1)
	{
		targetWall = walls[0];
	}
	else if (walls.size() > 1)
	{
		switch (wallPosition)
		{
		case emVertical:
		case emHorizontal:
			targetWall = _findTargetWall1(walls, wallPosition);
			break;
		case emLeft:
		case emRight:
		case emTop:
		case emBottom:
			targetWall = _findTargetWall2(walls, wallPosition, space1->id(), number);
			break;
		default:
			targetWall = walls[0];
			break;
		}
	}

	if (targetWall)
	{
		targetWall->setConnectionType(type);
		targetWall->opening()->setWidth(width);
		targetWall->opening()->setHeight(height);
		return true;
	}

	return false;
}

bool Storey::findConnections(WallPtrs& walls, int spaceId1, int spaceId2)
{
	walls.clear();
	if (spaceId1 == spaceId2)
		return false;

	// - 获取对应的Face
	int faceId1 = 0, faceId2 = 0;
	if (_spaces.findFace(faceId1, spaceId1) == false || _spaces.findFace(faceId2, spaceId2) == false)
		return false;

	Face face1 = _layoutNet->getFace(faceId1);
	Face face2 = _layoutNet->getFace(faceId2);

	// - 遍历
	Arr_Face* face1_ = static_cast<Arr_Face*>(face1.pointer());
	Arr_Face* face2_ = static_cast<Arr_Face*>(face2.pointer());

	// -- 获取两个face的遍历器，调整先后顺序，保证非unbounded的面为it1。
	Arrangement_2::Ccb_halfedge_circulator it1, it2;
	if (face1_->is_unbounded())
	{
		it1 = face2_->outer_ccb();
		it2 = *face1_->inner_ccbs_begin();
	}
	else if (face2_->is_unbounded())
	{
		it1 = face1_->outer_ccb();
		it2 = *face2_->inner_ccbs_begin();
	}
	else
	{
		it1 = face1_->outer_ccb();
		it2 = face2_->outer_ccb();
	}

	// -- 遍历两个face的外边框，找到共边
	Arrangement_2::Ccb_halfedge_circulator it1_first = it1, it2_first = it2;
	do
	{
		Arr_Halfedge_handle h1 = it1;
		do
		{
			Arr_Halfedge_handle h2 = it2;
			if (h1 == h2->twin())
			{
				LinearWall* wall = _walls.find(Edge(static_cast<void*>(&h1)));
				if(wall)
					walls.push_back(wall);
			}

			++it2;
		} while (it2 != it2_first);

		++it1;
	} while (it1 != it1_first);

	if (walls.size() == 0)
		return false;
	return true;
}

WallPtrs Storey::findSurroundedWalls(int spaceId)
{
	WallPtrs walls;

	// - 获取face
	int faceId = 0;
	if (_spaces.findFace(faceId, spaceId) == false)
		return walls;

	Face face = _layoutNet->getFace(faceId);
	if (face.isUnbounded())
		return walls;

	// - 判断是否为union
	SpacePtrs spaces = findUnion(spaceId);
	if (spaces.size() == 0)
	{
		// - 遍历face
		Arr_Face* face_ = static_cast<Arr_Face*>(face.pointer());
		Arrangement_2::Ccb_halfedge_circulator it = face_->outer_ccb();
		Arrangement_2::Ccb_halfedge_circulator it1_first = it;
		do
		{
			Arr_Halfedge_handle h1 = it;

			LinearWall* wall = _walls.find(Edge(static_cast<void*>(&h1)));
			if (wall)
				walls.push_back(wall);

			++it;
		} while (it != it1_first);

		return walls;
	}
	else
	{
		std::vector<Arr_Halfedge_handle> halfedges;

		std::set<Arr_Face_handle> faces;
		Arr_Face *arr_face = static_cast<Arr_Face*>(face.pointer());
		faces.insert(Arr_Face_handle(arr_face));
		for (int i = 0; i < spaces.size(); ++i)
		{
			int faceId1 = 0;
			if (_spaces.findFace(faceId1, spaces[i]->id()) == false)
				continue;

			Face face1 = _layoutNet->getFace(faceId1);
			Arr_Face* arr_face1 = static_cast<Arr_Face*>(face1.pointer());
			faces.insert(Arr_Face_handle(arr_face1));
		}

		// - 获取几个face的外边
		if (cgalUtilities::get_outer_loop_of(faces, *(Arrangement_2*)_layoutNet->arrangement(), halfedges) == false)
			return walls;

		// - 遍历半边返回wall
		for (size_t i = 0; i < halfedges.size(); ++i)
		{
			Arr_Halfedge_handle h1 = halfedges[i];
			LinearWall* wall = _walls.find(Edge(static_cast<void*>(&h1)));
			if (wall)
				walls.push_back(wall);
		}

		return walls;
	}
}

SpacePtrs Storey::findUnion(int spaceId)
{
	SpacePtrs spaces;

	// - 获取space
	int faceId = 0;
	if (_spaces.findFace(faceId, spaceId) == false)
		return spaces;

	Face face = _layoutNet->getFace(faceId);
	if (face.isUnbounded())
		return spaces;

	// - 遍历face
	Arr_Face* face_ = static_cast<Arr_Face*>(face.pointer());
	Arrangement_2::Ccb_halfedge_circulator it = face_->outer_ccb();
	Arrangement_2::Ccb_halfedge_circulator it1_first = it;
	do
	{
		Arr_Halfedge_handle h1 = it;

		LinearWall* wall = _walls.find(Edge(static_cast<void*>(&h1)));
		if (wall)
		{
			if (wall->connectionType() == Wall::ConnectionType::emUnion)
			{
				Space* space1 = nullptr;
				Space* space2 = nullptr;
				if (findSpaces(space1, space2, *wall))
				{
					if (space1->id() != spaceId)
						spaces.push_back(space1);
					else
						spaces.push_back(space2);
				}
			}
		}

		++it;
	} while (it != it1_first);

	return spaces;
}

LayoutNet* Storey::layoutNet()
{
	return _layoutNet;
}

const LayoutNet* Storey::layoutNet() const
{
	return _layoutNet;
}

Polygon2d Storey::footprint() const
{
	Polygon2d loop;
	_layoutNet->outmostLoop(loop);
	return loop;
}

bool Storey::modelling(CompoundBody& shapes) const
{
	//_test();
	// 墙建模
	for (int i = 0; i < _walls.size(); ++i)
	{
		const LinearWall& wall = _walls[i];
		if (wall.connectionType() == Wall::emUnion)
			continue;

		// --- 创建实体
		Body body;
		if (wall.modelling(body) == false)
			continue;

		// -- 将 Body 对象添加到 CompoundBody
		shapes.push_back(body);
	}

	// 板建模
	for (int i = 0; i < _spaces.size(); ++i)
	{
		const Space& space = _spaces[i];
		if(space.isUnbounded())
			continue;

		Space::SpaceType spaceType = space.spaceType();

		// 地板
		if (spaceType != Space::emCourtyard)
		{
			Body body0;
			if (space.floor().modelling(body0) == false)
				continue;
			shapes.push_back(body0);
		}

		// 天花板
		if (spaceType == Space::emInnerSpace)
		{
			Body body1;
			if (space.roof().modelling(body1) == false)
				continue;
			shapes.push_back(body1);
		}
	}

	return shapes.bodyCount() > 0;
}

Storey& Storey::operator=(const Storey& src)
{
	if (this == &src)
		return *this;

	SpatialElement::operator=(src);
	_height = src._height;
	_elevation = src._elevation;
	*_layoutNet = *src._layoutNet;
	_spaces = src._spaces;
	_walls = src._walls;

	return *this;
}

meta_impl::Direction2d Storey::_directionInSpace(int wallId, int space1Id)
{
	Direction2d direction;
	int edgeId = 0;
	if (_walls.findEdge(edgeId, wallId))
	{
		Halfedge he = _layoutNet->getHalfedge(edgeId);
		Face face = he.face();

		Space* space_ = _spaces.findFromFace(face.id());
		if (space_)
		{
			Point2d sourse = he.source().point();
			Point2d target = he.target().point();
			if (space_->id() == space1Id)
			{
				direction = (target - sourse).toDirection();
			}
			else
			{
				direction = (sourse - target).toDirection();
			}
		}
	}
	return direction;
}

Wall* Storey::_findTargetWall1(WallPtrs walls, Position wallPosition)
{
	Wall* target = nullptr;
	for (int i = 0; i < walls.size(); ++i)
	{
		Wall* wall = walls[i];
		if (wall->type() != Wall::emLinearWall)
			continue;

		LinearWall* wall_ = static_cast<LinearWall*>(wall);
		switch (wallPosition)
		{
		case emVertical:
		{
			if (wall_->is_vertical())
				target = wall_;
		}
		break;
		case emHorizontal:
		{
			if (wall_->is_horizontal())
				target = wall_;
		}
		break;
		default:
			break;
		}
	}
	return target;
}

Wall* Storey::_findTargetWall2(WallPtrs walls, Position wallPosition, int spaceId, int number)
{
	if (walls.size() == 0)
		return nullptr;

	Wall* target = nullptr;

	// - 找到相应left/right/top/bottom 的 walls
	std::map<double, LinearWall*> walls_;
	for (int i = 0; i < walls.size(); ++i)
	{
		Wall* wall = walls[i];
		if (wall->type() != Wall::emLinearWall)
			continue;

		LinearWall* wall_ = static_cast<LinearWall*>(wall);
		Point2d position = wall_->positionId();
		switch (wallPosition)
		{
		case emLeft:
		{
			Direction2d left(0, -1);
			Direction2d direction = _directionInSpace(wall_->id(), spaceId);
			if (direction.isEqualTo(left))
			{
				walls_.insert(std::make_pair(position.y, wall_));
			}
		}
			break;
		case emRight:
		{
			Direction2d left(0, 1);
			Direction2d direction = _directionInSpace(wall_->id(), spaceId);
			if (direction.isEqualTo(left))
			{
				walls_.insert(std::make_pair(position.y, wall_));
			}
		}
			break;
		case emTop:
		{
			Direction2d left(-1, 0);
			Direction2d direction = _directionInSpace(wall_->id(), spaceId);
			if (direction.isEqualTo(left))
			{
				walls_.insert(std::make_pair(position.x, wall_));
			}
		}
			break;
		case emBottom:
		{
			Direction2d left(1, 0);
			Direction2d direction = _directionInSpace(wall_->id(), spaceId);
			if (direction.isEqualTo(left))
			{
				walls_.insert(std::make_pair(position.x, wall_));
			}
		}
			break;
		default:
			break;
		}
	}

	// - 获取第number个
	if (walls_.size() > 0)
	{
		if (number <= 0)
		{
			target = walls_.begin()->second;
		}
		else
		{
			number -= 1; // 对齐计算机数组从0开始计算的规则
			if (walls_.size() > number)
				target = MyUtilities::get(walls_, number);
		}
	}

	return target;
}

void meta_impl::Storey::_test() const
{
	// 遍历楼层中所有的空间
	for (int i = 0; i < _spaces.size(); ++i)
	{
		const Space& space = _spaces[i];
		if (space.isUnbounded())
			continue;

		std::ostringstream oss;

		// - 输出空间的基本信息
		MyString name = space.name();
		int spaceId = space.id();

		// -- 将信息格式化为字符串
		oss << "Space Name: " << name.c_str() << ", Space ID: " << spaceId;


		// - 输出空间所附着的face
		Face face;
		if (findFace(face, spaceId) == false)
			continue;
		int faceId = face.id();

		// -- 将信息格式化为字符串
		oss << ", Face ID: " << faceId << "\n";

		// -- 遍历face所有的halfedges
		Arr_Face* face_ = static_cast<Arr_Face*>(face.pointer());
		Arrangement_2::Ccb_halfedge_circulator it = face_->outer_ccb();
		Arrangement_2::Ccb_halfedge_circulator it_first = it;
		do
		{
			Arr_Halfedge_handle h1 = it;
			const LinearWall* wall = _walls.find(Edge(static_cast<void*>(&h1)));
			if (wall != nullptr)
			{
				oss << "Wall ID: " << wall->id();
			}

			oss << "; Source: " << cgalUtilities::from(h1->source()->point()).c_str();
			oss << ", Target: " << cgalUtilities::from(h1->target()->point()).c_str() << "\n";

			++it;
		} while (it != it_first);

		// - 输出到 Debug 页面
		MyUtilities::printToDebugWindow(oss.str());
	}
}

class Storeys::Impl
{
public:
	void init(int n)
	{
		_storeys.clear();
		for (int i = 0; i < n; ++i)
		{
			_storeys.push_back(Storey());
		}
	}

	void reset(int n)
	{
		init(n);
	}

	void clear()
	{
		_storeys.clear();
	}

	int push_back(const Storey& storey)
	{
		_storeys.push_back(storey);
		return int(_storeys.size() - 1);
	}

	int size() const
	{
		return (int)_storeys.size();
	}

	Storey& operator[](int n)
	{
		return _storeys[n];
	}

	const Storey& operator[](int n) const
	{
		return _storeys[n];
	}

private:
	std::vector<Storey> _storeys;
};

Storeys::Storeys()
	: _impl(new Impl())
{

}

Storeys::Storeys(const Storeys& src)
	: _impl(new Impl(*src._impl))
{

}

Storeys::~Storeys()
{
	delete _impl;
}

void Storeys::init(int n)
{
	return _impl->init(n);
}

void Storeys::clear()
{
	_impl->clear();
}

int Storeys::size() const
{
	return _impl->size();
}

Storeys& Storeys::operator=(const Storeys& src)
{
	*_impl = *src._impl;
	return *this;
}

Storey& Storeys::operator[](int n)
{
	return (*_impl)[n];
}

const Storey& Storeys::operator[](int n) const
{
	return (*_impl)[n];
}

Building::Building()
	: SpatialElement()
{

}

Building::Building(const Building& src)
	: SpatialElement(src)
	, _storeys(src._storeys)
{

}

Building::~Building()
{

}

Root::ObjectType Building::desc()
{
	return Root::emBuilding;
}

bool Building::isKindOf(ObjectType objType) const
{
	if (objType == Root::emBuilding)
		return true;
	return SpatialElement::isKindOf(objType);
}

Root::ObjectType Building::type() const
{
	return Root::emBuilding;
}

Root* Building::copy() const
{
	return new Building(*this);
}

void Building::copyFrom(const Root* src)
{
	*this = *(static_cast<const Building*>(src));
}

void Building::initStoreys(int size)
{
	_storeys.init(size);
	for (int i = 0; i < _storeys.size(); ++i)
	{
		_storeys[i].setOwner(this);
	}
}

int Building::storeySize() const
{
	return _storeys.size();
}

Storey& Building::storey(int n)
{
	return _storeys[n];
}

const Storey& Building::storey(int n) const
{
	return _storeys[n];
}

bool Building::modelling(CompoundBody& shapes) const
{
	// Iterate over each storey in the building
	for (int i = 0; i < _storeys.size(); ++i)
	{
		const Storey& storey = this->storey(i);
		storey.modelling(shapes);
	}

	return true;
}

Polygon2d Building::footprint() const
{
	Polygon2d result;
	for (int i = 0; i < _storeys.size(); ++i)
	{
		const Storey& storey_ = storey(i);
		Polygon2d footprint1 = storey_.footprint();
		if (i == 0)
			result = footprint1;
		else
			result.unionWith(footprint1);
	}
	return result;
}

Building& Building::operator=(const Building& src)
{
	if (this == &src)
		return *this;

	SpatialElement::operator=(src);
	_storeys = src._storeys;
	return *this;
}

class Buildings::Impl
{
public:
	void init(int n)
	{
		_buildings.clear();
		for (int i = 0; i < n; ++i)
		{
			_buildings.push_back(Building());
		}
	}

	void reset(int n)
	{
		init(n);
	}

	void clear()
	{
		_buildings.clear();
	}

	int push_back(const Building& building)
	{
		_buildings.push_back(building);
		return int(_buildings.size() - 1);
	}

	int size() const
	{
		return (int)_buildings.size();
	}

	Building& operator[](int n)
	{
		return _buildings[n];
	}

	const Building& operator[](int n) const
	{
		return _buildings[n];
	}

private:
	std::vector<Building> _buildings;
};

Buildings::Buildings()
	: _impl(new Impl())
{

}

Buildings::Buildings(const Buildings& src)
	: _impl(new Impl(*src._impl))
{

}

Buildings::~Buildings()
{
	delete _impl;
}

void Buildings::init(int n)
{
	return _impl->init(n);
}

void Buildings::clear()
{
	_impl->clear();
}

int Buildings::size() const
{
	return _impl->size();
}

Buildings& Buildings::operator=(const Buildings& src)
{
	*_impl = *src._impl;
	return *this;
}

Building& Buildings::operator[](int n)
{
	return (*_impl)[n];
}

const Building& Buildings::operator[](int n) const
{
	return (*_impl)[n];
}

Site::Site()
	: SpatialElement()
{

}

Site::Site(const Site& src)
	: SpatialElement(src)
	, _buildings(src._buildings)
{

}

Site::~Site()
{

}

Root::ObjectType Site::desc()
{
	return Root::emSite;
}

bool Site::isKindOf(ObjectType objType) const
{
	if (objType == Root::emSite)
		return true;
	return SpatialElement::isKindOf(objType);
}

Root::ObjectType Site::type() const
{
	return Root::emSite;
}

Root* Site::copy() const
{
	return new Site(*this);
}

void Site::copyFrom(const Root* src)
{
	*this = *(static_cast<const Site*>(src));
}

void Site::initBuildings(int size)
{
	_buildings.init(size);
	for (int i = 0; i < _buildings.size(); ++i)
	{
		_buildings[i].setOwner(this);
	}
}

int Site::buildingSize() const
{
	return _buildings.size();
}

Building& Site::building(int n)
{
	return _buildings[n];
}

const Building& Site::building(int n) const
{
	return _buildings[n];
}

bool Site::modelling(CompoundBody& shapes) const
{
	// Iterate over each building in the site
	for (int i = 0; i < _buildings.size(); ++i)
	{
		const Building& building = _buildings[i];
		building.modelling(shapes);
	}

	return true; // If all modelling operations succeed, return true
}

Point2d Site::footprintCenter() const
{
	double minX = std::numeric_limits<double>::max();
	double minY = std::numeric_limits<double>::max();
	double maxX = std::numeric_limits<double>::lowest();
	double maxY = std::numeric_limits<double>::lowest();

	// 遍历所有建筑  
	for (int i = 0; i < buildingSize(); ++i) 
	{
		const Building& buildingInstance = building(i);

		// 遍历建筑的楼层  
		for (int j = 0; j < buildingInstance.storeySize(); ++j)
		{
			const Storey& storey = buildingInstance.storey(j);

			// 假设要处理的楼层是第一层  
			if (j == 0)
			{
				// 遍历第一层的所有空间
				for (int n1 = 0; n1 < storey.spaceSize(); ++n1)
				{
					const Space& space = storey.space(n1);

					// 获取空间的 footprint  
					Polygon2d footprint = space.footprint();

					// 获取 footprint 的边界  
					int pointCount = footprint.pointSize(); // 使用 pointSize() 获取点的数量  
					for (int n = 0; n < pointCount; ++n) {
						Point2d vertex = footprint.point(n); // 使用 point(n) 获取每个点  

						// 更新边界  
						if (vertex.x < minX) minX = vertex.x;
						if (vertex.y < minY) minY = vertex.y;
						if (vertex.x > maxX) maxX = vertex.x;
						if (vertex.y > maxY) maxY = vertex.y;
					}
				}
			}
		}
	}

	// 计算最小包围盒的中心点  
	if (minX == std::numeric_limits<double>::max() || minY == std::numeric_limits<double>::max()) {
		// 如果没有找到任何 footprint，返回一个默认点  
		return Point2d(0, 0); // 假定的默认值  
	}

	double centerX = (minX + maxX) / 2.0;
	double centerY = (minY + maxY) / 2.0;
	return Point2d(centerX, centerY);
}

Element* Site::find(const Point& position)
{
	Point2d xy(position.x, position.y);
	double elevation = position.z;

	// 遍历所有建筑
	for (int i = 0; i < buildingSize(); ++i)
	{
		Building& buildingInstance = building(i);

		// 遍历建筑的楼层
		for (int j = 0; j < buildingInstance.storeySize(); ++j)
		{
			Storey& storey = buildingInstance.storey(j);

			double elevation_ = storey.elevation();
			if (elevation < elevation_ - MyTol::dTol.equalPoint() || elevation > elevation_ + storey.height())
				continue;

			Element* element = storey.find(xy);
			if (element != nullptr)
				return element;
		}
	}

	return nullptr;
}

const Element* Site::find(const Point& position) const
{
	Point2d xy(position.x, position.y);
	double elevation = position.z;

	// 遍历所有建筑
	for (int i = 0; i < buildingSize(); ++i)
	{
		const Building& buildingInstance = building(i);

		// 遍历建筑的楼层
		for (int j = 0; j < buildingInstance.storeySize(); ++j)
		{
			const Storey& storey = buildingInstance.storey(j);

			double elevation_ = storey.elevation();
			if (elevation < elevation_ - MyTol::dTol.equalPoint() || elevation > elevation_ + storey.height())
				continue;

			const Element* element = storey.find(xy);
			if (element != nullptr)
				return element;
		}
	}

	return nullptr;
}

Element* Site::find(const TopoDS_Shape& shape)
{
	int id = 0;
	if (TopoDS_Shape_Map::singleton().find(id, shape) == false)
		return nullptr;

	for (int i = 0; i < buildingSize(); ++i)
	{
		Building& building = this->building(i);
		for (int j = 0; j < building.storeySize(); ++j)
		{
			Storey& storey = building.storey(j);
			LinearWall* wall = storey.getWall(id);
			if (wall != nullptr)
			{
				return wall;
			}

			Space* space = storey.getSpace(id);
			if (space != nullptr)
			{
				return &space->floor();
			}
		}
	}

	return nullptr;
}

const Element* Site::find(const TopoDS_Shape& shape) const
{
	int id = 0;
	if (TopoDS_Shape_Map::singleton().find(id, shape) == false)
		return nullptr;

	for (int i = 0; i < buildingSize(); ++i)
	{
		const Building& building = this->building(i);
		for (int j = 0; j < building.storeySize(); ++j)
		{
			const Storey& storey = building.storey(j);
			const LinearWall* wall = storey.getWall(id);
			if (wall != nullptr)
			{
				return wall;
			}

			const Space* space = storey.getSpace(id);
			if (space != nullptr)
			{
				return &space->floor();
			}
		}
	}

	return nullptr;
}

Site& Site::operator=(const Site& src)
{
	if (this == &src)
		return*this;

	SpatialElement::operator=(src);
	_buildings = src._buildings;
	return *this;
}
