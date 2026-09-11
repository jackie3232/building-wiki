#include "pch.h"
#include "IdCreator.h"

IdCreator IdCreator::_singleton;
IdCreator::IdCreator()
	: _n(100000000)
{

}

IdCreator& IdCreator::singleton()
{
	return _singleton;
}

int IdCreator::create()
{
	return (++_n);
}
