#pragma once
#include <TopTools_DataMapOfShapeInteger.hxx>

class TopoDS_Shape_Map
{
public:
	const static TopoDS_Shape_Map& singleton();

	void clear();
	void add(const TopoDS_Shape& shape, int id);
	bool find(int& id, const TopoDS_Shape& shape) const;

private:
	static TopoDS_Shape_Map _singleton;
	TopTools_DataMapOfShapeInteger _shape_id_map;
};

