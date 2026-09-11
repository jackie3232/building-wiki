#pragma once

class IdCreator
{
public:
	static IdCreator& singleton();
	int create();

private:
	IdCreator();

	static IdCreator _singleton;
	int _n;
};

