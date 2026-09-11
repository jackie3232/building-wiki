#pragma once
#include <string>

class MyWString;
class MyString
{
public:
	MODELLING_EXIMPORT MyString();
	MODELLING_EXIMPORT MyString(const MyString& s);
	MODELLING_EXIMPORT MyString(const char* s);
	MODELLING_EXIMPORT ~MyString();

	MODELLING_EXIMPORT MyString static from(int n);

	MODELLING_EXIMPORT void set(const char* str);
	MODELLING_EXIMPORT const char* c_str() const;
	MODELLING_EXIMPORT int size() const;
	MODELLING_EXIMPORT MyWString toWString() const;

	MODELLING_EXIMPORT bool contains(const char* s) const;

	MODELLING_EXIMPORT MyString& operator=(const char* s);
	MODELLING_EXIMPORT MyString& operator=(const MyString& s);
	MODELLING_EXIMPORT MyString& operator+=(const MyString& s);

private:
	class Impl;
	Impl* _impl;
};

class MyWString
{
public:
	MODELLING_EXIMPORT MyWString();
	MODELLING_EXIMPORT MyWString(const MyWString& src);
	MODELLING_EXIMPORT MyWString(const wchar_t* str);
	MODELLING_EXIMPORT ~MyWString();

	MODELLING_EXIMPORT void operator=(const MyWString& src);

	MODELLING_EXIMPORT void set(const wchar_t* str);
	MODELLING_EXIMPORT const wchar_t* c_str() const;
	MODELLING_EXIMPORT int size() const;
	MODELLING_EXIMPORT MyString toString() const;

private:
	class Impl;
	Impl* _impl;
};

