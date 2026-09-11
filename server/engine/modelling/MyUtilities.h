#pragma once
#include <map>
#include <vector>
#include "body.h"
#include <Quantity_Color.hxx>
#include "geometry.h"

namespace meta_impl
{
	class LinearWall;
}

class MyUtilities
{
public:
	static void createProfile(meta_impl::Polygon2d& profile, const meta_impl::LineSegment2d& midCurve, double thickness);
	static void createProfile(meta_impl::Polygon2d& profile, const meta_impl::Point2d& bottomLeft, const meta_impl::Point2d& topRight);
	static void createProfile(meta_impl::Polygon2d& profile, double length, double thickness);

	static meta_impl::LinearWall* get(const std::map<double, meta_impl::LinearWall*>& walls, int index);
	static std::string combine(const std::string& str, int n);
	static std::string combin(const std::string& str1, const std::string& str2);

	static void printToDebugWindow(const std::string& message);
	static void printToDebugWindow(const MyString& message);
};

