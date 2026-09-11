#include "pch.h"
#include "RandomColor.h"
#include <vector>
#include "Quantity_NameOfColor.hxx"
#include <algorithm>
#include <random>
#include <map>

namespace meta_impl
{
	class ColorManager
	{
	public:
		ColorManager()
			: gen(std::random_device{}())
		{
			// 假设 Quantity_NOC_WHITE 是最后一个颜色  
			size_t totalColors = Quantity_NOC_WHITE;

			// 填充可用颜色，排除黑色、白色和灰色  
			for (int colorIdx = 0; colorIdx < totalColors; ++colorIdx)
			{
				if (colorIdx == Quantity_NOC_BLACK || colorIdx == Quantity_NOC_WHITE ||
					(colorIdx >= Quantity_NOC_GRAY && colorIdx <= Quantity_NOC_GRAY99))
					continue;

				availableColors.push_back(static_cast<Quantity_NameOfColor>(colorIdx));
			}
		}

		bool findUnusedColor(Quantity_NameOfColor& color)
		{
			// 打乱可用颜色  
			std::shuffle(availableColors.begin(), availableColors.end(), gen);

			// 尝试寻找未使用的颜色  
			for (const auto& candidate : availableColors)
			{
				// 检查该颜色是否已被使用  
				bool isUsed = false;
				for (const auto& used : usedColors)
				{
					if (used.second == candidate)
					{
						isUsed = true;
						break;
					}
				}

				if (!isUsed)
				{
					color = candidate; // 找到未使用的颜色  
					return true; // 找到颜色  
				}
			}

			return false; // 如果没有找到未使用的颜色
		}

		void add(const std::string& name, Quantity_NameOfColor color)
		{
			// 将颜色与名称绑定  
			usedColors[name] = color;
		}


		std::vector<Quantity_NameOfColor> availableColors; // 可用颜色向量  
		std::map<std::string, Quantity_NameOfColor> usedColors; // 已使用颜色  
		std::mt19937 gen; // 随机数生成器  
	};

	RandomColor RandomColor::_singleton;
	RandomColor::RandomColor()
		: _colorManager(new ColorManager())
	{

	}

	RandomColor::RandomColor(const RandomColor& src)
		: _colorManager(new ColorManager(*src._colorManager))
	{

	}

	RandomColor::~RandomColor()
	{
		delete _colorManager;
	}

	RandomColor& RandomColor::singleton()
	{
		return _singleton;
	}

	int RandomColor::color(const char* name)
	{
		Quantity_NameOfColor selectedColor;
		std::string colorName(name); // 将输入的 C 风格字符串转换为 std::string  

		// 先根据名字查找已经使用的颜色  
		auto it = _colorManager->usedColors.find(colorName);
		if (it != _colorManager->usedColors.end())
		{
			return it->second; // 返回已绑定的颜色  
		}

		// 如果颜色不存在，则调用 findUnusedColor 查找未使用的颜色  
		if (_colorManager->findUnusedColor(selectedColor))
		{
			_colorManager->usedColors[colorName] = selectedColor; // 将新颜色与名称绑定  
			return selectedColor; // 返回新选的颜色  
		}

		// 如果没有剩余颜色，返回黑色作为回退选项  
		return Quantity_NOC_BLACK;
	}

	void RandomColor::add(const char* name, int index)
	{
		// 将颜色与名称绑定  
		_colorManager->add(name, static_cast<Quantity_NameOfColor>(index));
	}

	void RandomColor::operator=(const RandomColor& src)
	{
		*_colorManager = *src._colorManager;
	}
}
