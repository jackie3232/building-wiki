#include "pch.h"
#include "body.h"
#include "MyUtilities.h"
#include "MyOCC.hpp"
#include "mystring.h"
#include "geometry.h"
#include "occUtilities.h"

using namespace meta_impl;
Body::Body()
	: _name()
	, _shape(new TopoDS_Shape())
{

}

Body::Body(const Body& src)
	: _name(src._name)
	, _shape(new TopoDS_Shape(*src._shape))
{

}

Body::~Body()
{
	delete _shape;
}

void Body::setName(const char* s)
{
	_name.set(s);
}

const char* Body::name() const
{
	return _name.c_str();
}

MyWString Body::name_w() const
{
	return _name.toWString();
}

void Body::setShape(const TopoDS_Shape& shape)
{
	*_shape = shape;
}

const TopoDS_Shape& Body::shape() const
{
	return *_shape;
}

void Body::transformBy(const Matrix3d& matrix)
{
	gp_Trsf trsf = occUtilities::from(matrix);

	BRepBuilderAPI_Transform transformer(*_shape, trsf);
	*_shape = transformer.Shape();
}

Body& Body::operator=(const Body& src)
{
	_name = src._name;
	*_shape = *src._shape;
	return *this;
}

Body& Body::operator-(const Body& tool)
{
	BRepAlgoAPI_Cut brep(*_shape, *tool._shape);
	*_shape = brep.Shape();
	return *this;
}

Body* Body::copy() const
{
	return new Body(*this);
}

class Bodies::Impl
{
public:
	void clear()
	{
		_bodies.clear();
	}

	int push_back(const Body& body)
	{
		_bodies.push_back(body);
		int index = int(_bodies.size() - 1);

		return index;
	}

	int size() const
	{
		return (int)_bodies.size();
	}

	Body& operator[](int n)
	{
		return _bodies[n];
	}

	const Body& operator[](int n) const
	{
		return _bodies[n];
	}

private:
	std::vector<Body> _bodies;
};

Bodies::Bodies()
	: _impl(new Impl())
{

}

Bodies::Bodies(const Bodies& src)
	: _impl(new Impl(*src._impl))
{

}

Bodies::~Bodies()
{
	delete _impl;
}

Bodies& Bodies::operator=(const Bodies& src)
{
	*_impl = *src._impl;
	return *this;
}

Body& Bodies::operator[](int n)
{
	return (*_impl)[n];
}

const Body& Bodies::operator[](int n) const
{
	return (*_impl)[n];
}

int Bodies::push_back(const Body& body)
{
	return _impl->push_back(body);
}

void Bodies::clear()
{
	_impl->clear();
}

int Bodies::size() const
{
	return _impl->size();
}

CompoundBody::CompoundBody()
{

}

CompoundBody::CompoundBody(const CompoundBody& src)
	: _bodies(src._bodies)
{

}

CompoundBody::~CompoundBody()
{

}

void CompoundBody::push_back(const Body& shape)
{
	_bodies.push_back(shape);
}

int CompoundBody::bodyCount() const
{
	return _bodies.size();
}

Body& CompoundBody::body(int i)
{
	return _bodies[i];
}

const Body& CompoundBody::body(int i) const
{
	return _bodies[i];
}

CompoundBody& CompoundBody::operator=(const CompoundBody& src)
{
	_bodies = src._bodies;
	return *this;
}
