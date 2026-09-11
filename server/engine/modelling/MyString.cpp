#include "pch.h"
#include "mystring.h"
#include "MyUtilities.h"

#if !defined(_WIN32)
namespace {
// 最小 UTF-8 ⇄ wchar_t 转换（Linux 下仅用于调试输出路径，不影响几何语义）
std::wstring utf8ToW(const std::string& s)
{
	std::wstring out;
	out.reserve(s.size());
	for (size_t i = 0; i < s.size();)
	{
		unsigned char c = (unsigned char)s[i];
		unsigned int cp = 0; int extra = 0;
		if (c < 0x80)                { cp = c;        extra = 0; }
		else if ((c & 0xE0) == 0xC0) { cp = c & 0x1F; extra = 1; }
		else if ((c & 0xF0) == 0xE0) { cp = c & 0x0F; extra = 2; }
		else if ((c & 0xF8) == 0xF0) { cp = c & 0x07; extra = 3; }
		else                         { cp = 0xFFFD;   extra = 0; }

		if (i + (size_t)extra >= s.size()) { cp = 0xFFFD; extra = 0; }
		for (int k = 1; k <= extra; ++k)
			cp = (cp << 6) | ((unsigned char)s[i + k] & 0x3F);
		i += (size_t)extra + 1;
		out.push_back(static_cast<wchar_t>(cp));
	}
	return out;
}

std::string wToUtf8(const std::wstring& w)
{
	std::string out;
	for (wchar_t wc : w)
	{
		unsigned int cp = (unsigned int)wc;
		if (cp < 0x80)
			out.push_back((char)cp);
		else if (cp < 0x800)
		{
			out.push_back((char)(0xC0 | (cp >> 6)));
			out.push_back((char)(0x80 | (cp & 0x3F)));
		}
		else if (cp < 0x10000)
		{
			out.push_back((char)(0xE0 | (cp >> 12)));
			out.push_back((char)(0x80 | ((cp >> 6) & 0x3F)));
			out.push_back((char)(0x80 | (cp & 0x3F)));
		}
		else
		{
			out.push_back((char)(0xF0 | (cp >> 18)));
			out.push_back((char)(0x80 | ((cp >> 12) & 0x3F)));
			out.push_back((char)(0x80 | ((cp >> 6) & 0x3F)));
			out.push_back((char)(0x80 | (cp & 0x3F)));
		}
	}
	return out;
}
} // namespace
#endif

class MyString::Impl
{
public:
	Impl(){}
	Impl(const char* s)
		: str(s)
	{

	}
	std::string str;
};

MyString::MyString()
	: _impl(new Impl())
{

}

MyString::MyString(const MyString& s)
	: _impl(new Impl(*s._impl))
{

}

MyString::MyString(const char* s)
	: _impl(new Impl(s))
{

}

MyString::~MyString()
{
	delete _impl;
}

MyString MyString::from(int n)
{
	std::ostringstream oss;
	oss << n ;

	return MyString(oss.str().c_str());
}

void MyString::set(const char* str_)
{
	_impl->str = str_;
}

const char* MyString::c_str() const
{
	return _impl->str.c_str();
}

int MyString::size() const
{
	return (int)_impl->str.size();
}

MyWString MyString::toWString() const
{
#if defined(_WIN32)
	int size_needed = MultiByteToWideChar(CP_ACP, 0, _impl->str.c_str(), (int)_impl->str.size(), nullptr, 0);
	std::wstring wstr(size_needed, 0);
	MultiByteToWideChar(CP_ACP, 0, _impl->str.c_str(), (int)_impl->str.size(), &wstr[0], size_needed);

	return MyWString(wstr.c_str());
#else
	// 非 Windows：内部字符串统一为 UTF-8，直接按 UTF-8 解码
	return MyWString(utf8ToW(std::string(_impl->str)).c_str());
#endif
}

bool MyString::contains(const char* s) const
{
	std::string sub = s;
	if (_impl->str.find(sub) != std::string::npos)
		return true;
	return false;
}

MyString& MyString::operator=(const char* s)
{
	_impl->str = s;
	return *this;
}

MyString& MyString::operator=(const MyString& s)
{
	*_impl = *s._impl;
	return *this;
}

MyString& MyString::operator+=(const MyString& s)
{
	_impl->str += s._impl->str;
	return *this;
}

class MyWString::Impl
{
public:
	Impl(){}
	Impl(const wchar_t* str_)
		: str(str_)
	{

	}

	std::wstring str;
};

MyWString::MyWString()
	: _impl(new Impl())
{

}

MyWString::MyWString(const MyWString& src)
	: _impl(new Impl(*src._impl))
{

}

MyWString::MyWString(const wchar_t* str)
	: _impl(new Impl(str))
{

}

MyWString::~MyWString()
{
	delete _impl;
}

void MyWString::set(const wchar_t* str)
{
	_impl->str = str;
}

const wchar_t* MyWString::c_str() const
{
	return _impl->str.c_str();
}

int MyWString::size() const
{
	return (int)_impl->str.size();
}

MyString MyWString::toString() const
{
#if defined(_WIN32)
	int size_needed = WideCharToMultiByte(CP_ACP, 0, _impl->str.c_str(), (int)_impl->str.size(), nullptr, 0, nullptr, nullptr);
	std::string str(size_needed, 0);
	WideCharToMultiByte(CP_ACP, 0, _impl->str.c_str(), (int)_impl->str.size(), &str[0], size_needed, nullptr, nullptr);

	return MyString(str.c_str());
#else
	return MyString(wToUtf8(std::string(_impl->str)).c_str());
#endif
}

void MyWString::operator=(const MyWString& src)
{
	*_impl = *src._impl;
}
