#include "pch.h"
#include "TopoDS_Shape_Map.h"

TopoDS_Shape_Map TopoDS_Shape_Map::_singleton;
const TopoDS_Shape_Map& TopoDS_Shape_Map::singleton()
{
	return _singleton;
}

void TopoDS_Shape_Map::clear()
{
	_shape_id_map.Clear();
}

void TopoDS_Shape_Map::add(const TopoDS_Shape& shape, int id)
{
	_shape_id_map.Bind(shape, id);
}

bool TopoDS_Shape_Map::find(int& id, const TopoDS_Shape& shape) const
{
	return _shape_id_map.Find(shape, id);
}
