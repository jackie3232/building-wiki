#pragma once
#include "mystring.h"

class TopoDS_Shape;
namespace meta_impl
{
	class Matrix3d;
}

namespace meta_impl
{
	class Body
	{
	public:
		MODELLING_EXIMPORT Body();
		MODELLING_EXIMPORT Body(const Body& src);
		MODELLING_EXIMPORT ~Body();

		MODELLING_EXIMPORT void setName(const char* s);
		MODELLING_EXIMPORT const char* name() const;
		MODELLING_EXIMPORT MyWString name_w() const;

		MODELLING_EXIMPORT void setShape(const TopoDS_Shape& shape);
		MODELLING_EXIMPORT const TopoDS_Shape& shape() const;
		MODELLING_EXIMPORT void transformBy(const Matrix3d& matrix);
		MODELLING_EXIMPORT Body* copy() const; // 需要外部释放

		MODELLING_EXIMPORT Body& operator=(const Body& src);
		MODELLING_EXIMPORT Body& operator-(const Body& tool);

	private:
		MyString _name;
		TopoDS_Shape* _shape;
	};

	class Bodies
	{
	public:
		MODELLING_EXIMPORT Bodies();
		MODELLING_EXIMPORT Bodies(const Bodies& src);
		MODELLING_EXIMPORT ~Bodies();

		MODELLING_EXIMPORT int push_back(const Body& body);
		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT int size() const;

		MODELLING_EXIMPORT Bodies& operator=(const Bodies& src);
		MODELLING_EXIMPORT Body& operator[](int n);
		MODELLING_EXIMPORT const Body& operator[](int n) const;

	private:
		class Impl;
		Impl* _impl;
	};

	class CompoundBody
	{
	public:
		MODELLING_EXIMPORT CompoundBody();
		MODELLING_EXIMPORT CompoundBody(const CompoundBody& src);
		MODELLING_EXIMPORT ~CompoundBody();

		MODELLING_EXIMPORT void push_back(const Body& shape);
		MODELLING_EXIMPORT int bodyCount() const;

		MODELLING_EXIMPORT Body& body(int i);
		MODELLING_EXIMPORT const Body& body(int i) const;

		MODELLING_EXIMPORT CompoundBody& operator=(const CompoundBody& src);

	private:
		Bodies _bodies;
	};
}// namespace meta_impl

