#include "pch.h"
#include "modelling.h"
#include "BRepPrimAPI_MakeSphere.hxx"
#include "BRepPrimAPI_MakeBox.hxx"
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepPrimAPI_MakePrism.hxx>
#include "BRepBuilderAPI_MakeEdge.hxx"

using namespace meta_impl;
bool Modelling::createFace(meta_impl::Body& shape, const Polygon2d& polygon)
{
	// Ensure the polygon has enough points to form a face
	if (polygon.pointSize() < 3)
	{
		return false; // Not enough points to create a face
	}

	// Create a wire from the polygon points
	BRepBuilderAPI_MakeWire wireBuilder;
	for (int i = 0; i < polygon.pointSize(); ++i)
	{
		Point2d pnt1 = polygon.point(i);
		Point2d pnt2 = polygon.point((i + 1) % polygon.pointSize());

		gp_Pnt p1(pnt1.x, pnt1.y, 0.0);
		gp_Pnt p2(pnt2.x, pnt2.y, 0.0);

		wireBuilder.Add(BRepBuilderAPI_MakeEdge(p1, p2));
	}

	TopoDS_Wire wire = wireBuilder.Wire();
	if (wire.IsNull())
	{
		return false; // Failed to create wire
	}

	// Create a face from the wire
	TopoDS_Face face = BRepBuilderAPI_MakeFace(wire);
	if (face.IsNull())
	{
		return false; // Failed to create face
	}

	// Set the face as the shape of the body
	shape.setShape(face);

	return true;
}

bool Modelling::sphere(meta_impl::Body& shape, double radius, Point origin)
{
	const TopoDS_Shape& _shape = BRepPrimAPI_MakeSphere(gp_Pnt(origin.x, origin.y, origin.z), radius);
	shape.setShape(_shape);
	return true;
}

bool Modelling::extrude(meta_impl::Body& shape, const Polygon2d& profile, double height, double elevation)
{
	if (profile.pointSize() < 3)
	{
		return false; // 多边形顶点数不够
	}

	BRepBuilderAPI_MakePolygon makePolygon;
	for (int i = 0; i < profile.pointSize(); ++i) 
	{
		Point2d pnt = profile.point(i);
		makePolygon.Add(gp_Pnt(pnt.x, pnt.y, elevation));
	}
	makePolygon.Close();

	if (!makePolygon.IsDone()) 
	{
		return false; // 多边形生成失败
	}

	TopoDS_Wire wire = makePolygon.Wire();
	BRepBuilderAPI_MakeFace makeFace(wire);

	if (!makeFace.IsDone()) 
	{
		return false; // 面生成失败
	}

	TopoDS_Face face = makeFace.Face();
	gp_Vec extrusionVec(0.0, 0.0, height);
	BRepPrimAPI_MakePrism makePrism(face, extrusionVec);

	if (!makePrism.IsDone()) 
	{
		return false; // 拉伸失败
	}

	const TopoDS_Shape& _shape = makePrism.Shape();
	shape.setShape(_shape);
	return true;
}
