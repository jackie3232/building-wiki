#pragma once

namespace meta_impl
{
	class Matrix3d;
}
class gp_Trsf;
class occUtilities
{
public:
	static gp_Trsf from(const meta_impl::Matrix3d& mat);
};

