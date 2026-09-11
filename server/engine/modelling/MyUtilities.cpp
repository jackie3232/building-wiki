#include "pch.h"
#include "MyUtilities.h"
#include "geometry.h"
#include "mystring.h"
#include <cstdio>

using namespace meta_impl;
void MyUtilities::createProfile(Polygon2d& profile, const LineSegment2d& midCurve, double thickness)
{
	// 获取 midCurve 的起点和终点
    Point2d start = midCurve.start(); // 起点
    Point2d end = midCurve.end();     // 终点
    
    // 计算 midCurve 的方向向量
    double dir_x = end.x - start.x;
    double dir_y = end.y - start.y;
    
    // 规范化方向向量
    Direction2d direction(dir_x, dir_y);
	dir_x = direction.x;
	dir_y = direction.y;
    
    // 计算垂直方向向量（旋转90度）
    double perp_x = -dir_y;
    double perp_y = dir_x;
    
    // 将垂直向量按宽度的一半进行缩放
    perp_x *= thickness / 2;
    perp_y *= thickness / 2;
    
    // 计算轮廓多边形的四个角点
    Point2d p1(start.x + perp_x, start.y + perp_y); // 左上角
    Point2d p2(start.x - perp_x, start.y - perp_y); // 左下角
    Point2d p3(end.x - perp_x, end.y - perp_y);     // 右下角
    Point2d p4(end.x + perp_x, end.y + perp_y);     // 右上角
    
    // 按逆时针顺序将点添加到轮廓多边形中
    profile.push_back(p1); // 左上角
    profile.push_back(p2); // 左下角
    profile.push_back(p3); // 右下角
    profile.push_back(p4); // 右上角
}

void MyUtilities::createProfile(Polygon2d& profile, const Point2d& bottomLeft, const Point2d& topRight)
{
	// 清空现有的多边形数据  
	profile.clear();

	// 获取矩形的其他两个顶点  
	Point2d bottomRight(topRight.x, bottomLeft.y); // 底部右侧点  
	Point2d topLeft(bottomLeft.x, topRight.y);      // 顶部左侧点  

	// 按逆时针顺序添加四个顶点，会形成一个矩形  
	profile.push_back(bottomLeft);    // 左下角  
	profile.push_back(bottomRight);   // 右下角  
	profile.push_back(topRight);      // 右上角  
	profile.push_back(topLeft);       // 左上角
}

void MyUtilities::createProfile(Polygon2d& profile, double length, double thickness)
{
    // 清空之前的点，以确保构造的多边形是新的  
    profile.clear();

    // 定义矩形的四个点，以 (0, 0) 为中心  
    Point2d bottomLeft(-length / 2.0, -thickness / 2.0); // 左下角  
    Point2d bottomRight(length / 2.0, -thickness / 2.0); // 右下角  
    Point2d topRight(length / 2.0, thickness / 2.0);    // 右上角  
    Point2d topLeft(-length / 2.0, thickness / 2.0);     // 左上角  

    // 添加矩形的四个顶点  
    profile.push_back(bottomLeft);
    profile.push_back(bottomRight);
    profile.push_back(topRight);
    profile.push_back(topLeft);
}

LinearWall* MyUtilities::get(const std::map<double, LinearWall*>& walls, int index)
{
    int i = 0;
    std::map<double, LinearWall*>::const_iterator it = walls.begin();
    for (; it != walls.end(); ++it)
    {
        if (i++ == index)
        {
            return it->second;
        }
    }

    return nullptr;
}

std::string MyUtilities::combine(const std::string& str, int n)
{
    // 将整数 n 转换为字符串
    std::ostringstream oss;
    oss << n;
    std::string numberStr = oss.str();

    // 将 str 和 numberStr 组合起来
    return str + numberStr;
}

std::string MyUtilities::combin(const std::string& str1, const std::string& str2)
{
    return str1 + str2;
}

void MyUtilities::printToDebugWindow(const std::string& message)
{
#if defined(_WIN32)
    std::wstring wstr = MyString(message.c_str()).toWString().c_str();
    OutputDebugString(wstr.c_str());
#else
    std::fprintf(stderr, "%s", message.c_str());
#endif
}

void MyUtilities::printToDebugWindow(const MyString& message)
{
#if defined(_WIN32)
    std::wstring wstr = message.toWString().c_str();
    OutputDebugString(wstr.c_str());
#else
    std::fprintf(stderr, "%s", message.c_str());
#endif
}
