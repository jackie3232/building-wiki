#pragma once

namespace meta_impl
{
	// 随机颜色
	class ColorManager;
	class RandomColor
	{
	public:
		MODELLING_EXIMPORT static RandomColor& singleton();

		MODELLING_EXIMPORT int color(const char* name);
		MODELLING_EXIMPORT void add(const char* name, int index);

		MODELLING_EXIMPORT void operator=(const RandomColor& src);

	private:
		RandomColor();
		RandomColor(const RandomColor& src);
		~RandomColor();

		static RandomColor _singleton;
		ColorManager* _colorManager; // 颜色管理器实例
	};
}

