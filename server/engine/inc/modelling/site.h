#pragma once
#include "body.h"
#include "geometry.h"
#include "topology.h"
#include "RandomColor.h"
#include "mystring.h"

namespace meta_impl
{
	class Root
	{
	public:
		enum ObjectType
		{
			emRoot,
			emSpatialElement,
			emSite,
			emBuilding,
			emStorey,
			emSpace,
			emElement,
			emWall,
			emLinearWall,
			emCircularWall,
			emSlab,
			emOpening,
			emDoorOpening,
			emWindowOpening
		};
		virtual ~Root();

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const = 0;

		MODELLING_EXIMPORT static Root* copy(const Root* src); // 需要外部释放
		MODELLING_EXIMPORT virtual Root* copy() const = 0; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src) = 0;

		MODELLING_EXIMPORT void setOwner(Root* owner);
		MODELLING_EXIMPORT Root* owner();
		MODELLING_EXIMPORT const Root* owner() const;
		MODELLING_EXIMPORT int id() const;

		MODELLING_EXIMPORT virtual void setName(const char* s);
		MODELLING_EXIMPORT const char* name() const;

	protected:
		Root();
		Root(const Root& src);
		Root& operator=(const Root& src);

		MyString _name;
		Root* _owner;

	private:
		int _id;
	};

	class OpeningElement :
		public Root
	{
	public:
		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;

		MODELLING_EXIMPORT void setWidth(double width);
		MODELLING_EXIMPORT double width() const;

		MODELLING_EXIMPORT void setHeight(double height);
		MODELLING_EXIMPORT double height() const;

	protected:
		OpeningElement();
		OpeningElement(double width, double height);
		OpeningElement(const OpeningElement& src);
		OpeningElement& operator=(const OpeningElement& src);

		double _width;
		double _height;
	};

	class DoorOpening :
		public OpeningElement
	{
	public:
		MODELLING_EXIMPORT static const double min_width;
		MODELLING_EXIMPORT static const double min_height;

		MODELLING_EXIMPORT DoorOpening();
		MODELLING_EXIMPORT DoorOpening(const DoorOpening& src);
		MODELLING_EXIMPORT DoorOpening& operator=(const DoorOpening& src);

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);
	};

	class WindowOpening :
		public OpeningElement
	{
	public:
		MODELLING_EXIMPORT WindowOpening();
		MODELLING_EXIMPORT WindowOpening(const WindowOpening& src);
		MODELLING_EXIMPORT WindowOpening& operator=(const WindowOpening& src);

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);
	};

	class SpatialElement;
	class Element :
		public Root
	{
	public:
		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;

		MODELLING_EXIMPORT virtual Point2d positionId() const = 0;
		MODELLING_EXIMPORT virtual bool modelling(Body& body) const = 0;

	protected:
		Element();
		Element(const Element& src);
		Element& operator=(const Element& src);
		virtual bool _addOpening(Body& body) const = 0;
	};

	class Slab
		: public Element
	{
	public:
		MODELLING_EXIMPORT Slab();
		MODELLING_EXIMPORT Slab(const Slab& src);
		MODELLING_EXIMPORT Slab& operator=(const Slab& src);

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);

		MODELLING_EXIMPORT void setProfile(const Polygon2d& profile);
		MODELLING_EXIMPORT const Polygon2d& profile() const;

		MODELLING_EXIMPORT static double thickness();

		MODELLING_EXIMPORT void setElevation(double elevation);
		MODELLING_EXIMPORT double elevation() const;

		MODELLING_EXIMPORT virtual Point2d positionId() const;
		MODELLING_EXIMPORT bool modelling(Body& body) const;

	private:
		virtual bool _addOpening(Body& body) const;

		static const double _thickness;
		Polygon2d _profile;
		double _elevation;
	};

	class Space;
	class Wall
		: public Element
	{
	public:
		enum ConnectionType
		{
			emNormal,
			emUnion,
			emDoor,
			emWindow
		};

		MODELLING_EXIMPORT virtual ~Wall();
		MODELLING_EXIMPORT static const double thickness;

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;

		MODELLING_EXIMPORT virtual void setAxis(const Segment2d* axis) = 0;

		// Get and set methods for elevation
		MODELLING_EXIMPORT void setElevation(double elevation);
		MODELLING_EXIMPORT double elevation() const;

		// Get and set methods for height
		MODELLING_EXIMPORT void setHeight(double height);
		MODELLING_EXIMPORT double height() const;

		MODELLING_EXIMPORT void setConnectionType(ConnectionType type);
		MODELLING_EXIMPORT ConnectionType connectionType() const;
		MODELLING_EXIMPORT OpeningElement* opening() const;

		MODELLING_EXIMPORT Space* space1();
		MODELLING_EXIMPORT const Space* space1() const;
		MODELLING_EXIMPORT Space* space2();
		MODELLING_EXIMPORT const Space* space2() const;

		MODELLING_EXIMPORT virtual bool modelling(Body& body) const;

	protected:
		Wall();
		Wall(const Wall& src);
		Wall& operator=(const Wall& src);

		double _elevation;
		double _height;
		ConnectionType _connectionType;
		OpeningElement* _opening;
	};

	class LinearWall
		: public Wall
	{
	public:
		MODELLING_EXIMPORT LinearWall();
		MODELLING_EXIMPORT LinearWall(const LinearWall& src);
		MODELLING_EXIMPORT LinearWall(const LineSegment2d& axis);

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);

		MODELLING_EXIMPORT virtual void setAxis(const Segment2d* axis);
		MODELLING_EXIMPORT LineSegment2d& axis();
		MODELLING_EXIMPORT const LineSegment2d& axis() const;

		MODELLING_EXIMPORT virtual Point2d positionId() const; // 墙中线的中点
		MODELLING_EXIMPORT virtual bool modelling(Body& body) const;

		MODELLING_EXIMPORT bool is_vertical() const;
		MODELLING_EXIMPORT bool is_horizontal() const;

		MODELLING_EXIMPORT LinearWall& operator=(const LinearWall& src);

	private:
		virtual bool _addOpening(Body& body) const;
		bool _addDoor(Body& body, double width, double height, double offset = 0) const;
		bool _addWindow(Body& body, double width, double height, double offset = 0) const;

		LineSegment2d _axis;
	};

	class CircularWall
		: public Wall
	{
	public:
		MODELLING_EXIMPORT CircularWall();
		MODELLING_EXIMPORT CircularWall(const CircularWall& src);
		MODELLING_EXIMPORT CircularWall(const CircArc2d& axis);

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);

		MODELLING_EXIMPORT virtual void setAxis(const Segment2d* axis);

		MODELLING_EXIMPORT virtual Point2d positionId() const; // 墙中线的中点
		MODELLING_EXIMPORT virtual bool modelling(Body& body) const;
		MODELLING_EXIMPORT CircularWall& operator=(const CircularWall& src);

	private:
		virtual bool _addOpening(Body& body) const;

		CircArc2d _axis;
	};

	// 当前阶段只处理直线段的墙
	class Walls
	{
	public:
		MODELLING_EXIMPORT Walls();
		MODELLING_EXIMPORT Walls(const Walls& src);
		MODELLING_EXIMPORT ~Walls();

		MODELLING_EXIMPORT int push_back(const LinearWall& wall);
		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT int size() const;
		MODELLING_EXIMPORT void insert(const Edge& edge, int index);

		MODELLING_EXIMPORT LinearWall* find(const Edge& edge);
		MODELLING_EXIMPORT const LinearWall* find(const Edge& edge) const;

		MODELLING_EXIMPORT LinearWall* get(int wallId);
		MODELLING_EXIMPORT const LinearWall* get(int wallId) const;

		MODELLING_EXIMPORT bool findEdge(int& edgeId, int wallId);
		MODELLING_EXIMPORT bool findEdge(int& edgeId, int wallId) const;

		MODELLING_EXIMPORT Walls& operator=(const Walls& src);
		MODELLING_EXIMPORT LinearWall& operator[](int n);
		MODELLING_EXIMPORT const LinearWall& operator[](int n) const;

	private:
		class Impl;
		Impl* _impl;
	};

	class ObjectPtrs
	{
	public:
		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT int size() const;
		MODELLING_EXIMPORT ObjectPtrs* copy() const;

	protected:
		MODELLING_EXIMPORT ObjectPtrs();
		MODELLING_EXIMPORT ObjectPtrs(const ObjectPtrs& src);
		MODELLING_EXIMPORT virtual ~ObjectPtrs();

		MODELLING_EXIMPORT virtual void push_back(Root* wall);
		MODELLING_EXIMPORT virtual void insert_at_begin(Root* wall);

		MODELLING_EXIMPORT ObjectPtrs& operator=(const ObjectPtrs& src);

		class Impl;
		Impl* _impl;
	};

	class WallPtrs :
		public ObjectPtrs
	{
	public:
		MODELLING_EXIMPORT WallPtrs();
		MODELLING_EXIMPORT WallPtrs(const WallPtrs& src);
		MODELLING_EXIMPORT ~WallPtrs();

		MODELLING_EXIMPORT virtual void push_back(LinearWall* wall);
		MODELLING_EXIMPORT virtual void insert_at_begin(LinearWall* wall);

		MODELLING_EXIMPORT LinearWall* find(const Point2d& position);
		MODELLING_EXIMPORT const LinearWall* find(const Point2d& position) const;

		MODELLING_EXIMPORT LinearWall* operator[](int n);
		MODELLING_EXIMPORT const LinearWall* operator[](int n) const;
		MODELLING_EXIMPORT WallPtrs& operator=(const WallPtrs& src);
	};

	class SpacePtrs :
		public ObjectPtrs
	{
	public:
		MODELLING_EXIMPORT SpacePtrs();
		MODELLING_EXIMPORT SpacePtrs(const SpacePtrs& src);
		MODELLING_EXIMPORT ~SpacePtrs();

		MODELLING_EXIMPORT virtual void push_back(Space* wall);
		MODELLING_EXIMPORT virtual void insert_at_begin(Space* wall);

		MODELLING_EXIMPORT Space* operator[](int n);
		MODELLING_EXIMPORT const Space* operator[](int n) const;
		MODELLING_EXIMPORT SpacePtrs& operator=(const SpacePtrs& src);
	};

	class SpatialElement :
		public Root
	{
	public:
		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;

		MODELLING_EXIMPORT virtual void setFootprint(const Polygon2d& footprint);
		MODELLING_EXIMPORT Polygon2d& footprint();
		MODELLING_EXIMPORT const Polygon2d& footprint() const;

	protected:
		SpatialElement();
		SpatialElement(const SpatialElement& src);
		SpatialElement& operator=(const SpatialElement& src);

		Polygon2d _footprint;
	};

	class Space :
		public SpatialElement
	{
	public:
		enum SpaceType
		{
			emInnerSpace, // 室内
			emBalcony,  // 阳台
			emCourtyard,  // 庭院
			emOuterSpace // 外部
		};

		MODELLING_EXIMPORT Space();
		MODELLING_EXIMPORT Space(const Space& src);
		MODELLING_EXIMPORT ~Space();

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual void setName(const char* s);
		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);

		MODELLING_EXIMPORT void setSpaceType(SpaceType type);
		MODELLING_EXIMPORT SpaceType spaceType() const;
		MODELLING_EXIMPORT static const char* spaceTypeName(SpaceType type);

		MODELLING_EXIMPORT virtual void setFootprint(const Polygon2d& footprint);

		MODELLING_EXIMPORT void setIsUnbounded(bool unbounded);
		MODELLING_EXIMPORT bool isUnbounded() const;

		MODELLING_EXIMPORT void setHeight(double height);
		MODELLING_EXIMPORT double height() const;

		MODELLING_EXIMPORT void setElevation(double elevation);
		MODELLING_EXIMPORT double elevation() const;

		MODELLING_EXIMPORT Slab& floor();
		MODELLING_EXIMPORT const Slab& floor() const;

		MODELLING_EXIMPORT Slab& roof();
		MODELLING_EXIMPORT const Slab& roof() const;

		MODELLING_EXIMPORT Space& operator=(const Space& src);

		MODELLING_EXIMPORT bool modelling(Body& shape) const;
		MODELLING_EXIMPORT bool footprint_modelling(Body& face) const;
		MODELLING_EXIMPORT bool drawName(Body& txt) const;

	private:
		void _match_space_type();

		SpaceType _spaceType;
		bool _is_unbounded;
		Slab _floor;
		Slab _roof;
		int _face_id;

		double _height;
		double _elevation; // 底标高
	};

	class Spaces
	{
	public:
		MODELLING_EXIMPORT Spaces();
		MODELLING_EXIMPORT Spaces(const Spaces& src);
		MODELLING_EXIMPORT ~Spaces();

		MODELLING_EXIMPORT int push_back(const Space& space);
		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT int size() const;
		MODELLING_EXIMPORT void insert(int faceId, int spaceIndex);

		MODELLING_EXIMPORT Space* get(const char* name);
		MODELLING_EXIMPORT const Space* get(const char* name) const;

		MODELLING_EXIMPORT Space* get(int spaceId);
		MODELLING_EXIMPORT const Space* get(int spaceId) const;

		MODELLING_EXIMPORT Space* findFromFace(int faceId);
		MODELLING_EXIMPORT const Space* findFromFace(int faceId) const;

		MODELLING_EXIMPORT bool findFace(int& faceId, int spaceId);
		MODELLING_EXIMPORT bool findFace(int& faceId, int spaceId) const;

		MODELLING_EXIMPORT Spaces& operator=(const Spaces& src);
		MODELLING_EXIMPORT Space& operator[](int n);
		MODELLING_EXIMPORT const Space& operator[](int n) const;

	private:
		class Impl;
		Impl* _impl;
	};

	class LayoutNet;
	class Storey :
		public SpatialElement
	{
	public:
		enum Position
		{
			emNotSet,
			emVertical,
			emHorizontal,
			emLeft,
			emRight,
			emTop,
			emBottom
		};

		MODELLING_EXIMPORT Storey();
		MODELLING_EXIMPORT Storey(const Storey& src);
		MODELLING_EXIMPORT ~Storey();

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);

		MODELLING_EXIMPORT void setHeight(double height);
		MODELLING_EXIMPORT double height() const;

		MODELLING_EXIMPORT void setElevation(double elevation);
		MODELLING_EXIMPORT double elevation() const;

		MODELLING_EXIMPORT Space& addSpace(const Space& space);
		MODELLING_EXIMPORT int spaceSize() const;
		MODELLING_EXIMPORT Space& space(int n);
		MODELLING_EXIMPORT const Space& space(int n) const;
		MODELLING_EXIMPORT Space* getSpace(int spaceId);
		MODELLING_EXIMPORT const Space* getSpace(int spaceId) const;
		MODELLING_EXIMPORT Space* findSpace(const Face& face);
		MODELLING_EXIMPORT const Space* findSpace(const Face& face) const;

		MODELLING_EXIMPORT bool findFace(int& faceId, int spaceId);
		MODELLING_EXIMPORT bool findFace(int& faceId, int spaceId) const;
		MODELLING_EXIMPORT bool findFace(Face& face, int spaceId) const;

		MODELLING_EXIMPORT void refreshLayoutNet();
		MODELLING_EXIMPORT int createWalls();

		MODELLING_EXIMPORT int wallSize() const;
		MODELLING_EXIMPORT LinearWall& wall(int n);
		MODELLING_EXIMPORT const LinearWall& wall(int n) const;
		MODELLING_EXIMPORT LinearWall* getWall(int wallId);
		MODELLING_EXIMPORT const LinearWall* getWall(int wallId) const;
		MODELLING_EXIMPORT bool findEdge(Edge& edge, int wallId);
		MODELLING_EXIMPORT bool findEdge(Edge& edge, int wallId) const;

		MODELLING_EXIMPORT bool findSpaces(Space*& space1, Space*& space2, const LinearWall& wall);
		MODELLING_EXIMPORT bool findSpaces(Space*& space1, Space*& space2, const Edge& wallAxis);

		MODELLING_EXIMPORT bool isBalconyWall(const LinearWall& wall);
		MODELLING_EXIMPORT bool isBalconyWall(const Edge& wallAxis);

		MODELLING_EXIMPORT Element* find(const Point2d& position); // 根据构件的origin查找
		MODELLING_EXIMPORT const Element* find(const Point2d& position) const; // 根据构件的origin查找

		MODELLING_EXIMPORT Element* find(int topologyId); // 根据edge face的Id找到相应的墙、板等构件

		MODELLING_EXIMPORT bool addConnection(const char* spaceName1, const char* spaceName2, 
			Wall::ConnectionType type, double width, double height, Position wallPosition = emNotSet, int number = -1);

		MODELLING_EXIMPORT bool findConnections(WallPtrs& walls, int spaceId1, int spaceId2);
		MODELLING_EXIMPORT WallPtrs findSurroundedWalls(int spaceId);
		MODELLING_EXIMPORT SpacePtrs findUnion(int spaceId);

		MODELLING_EXIMPORT LayoutNet* layoutNet();
		MODELLING_EXIMPORT const LayoutNet* layoutNet() const;
		MODELLING_EXIMPORT Polygon2d footprint() const;
		MODELLING_EXIMPORT bool modelling(CompoundBody& shapes) const;

		MODELLING_EXIMPORT Storey& operator=(const Storey& src);

	private:
		Direction2d _directionInSpace(int wallId, int space1Id);
		Wall* _findTargetWall1(WallPtrs walls, Position wallPosition); // vertical/horizontal
		Wall* _findTargetWall2(WallPtrs walls, Position wallPosition, int spaceId, int number); // left/right/top/bottom
		void _test() const;

		double _height;
		double _elevation; // 底标高

		LayoutNet* _layoutNet;
		Spaces _spaces;
		Walls _walls;
	};

	class Storeys
	{
	public:
		MODELLING_EXIMPORT Storeys();
		MODELLING_EXIMPORT Storeys(const Storeys& src);
		MODELLING_EXIMPORT ~Storeys();

		MODELLING_EXIMPORT void init(int n);
		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT int size() const;

		MODELLING_EXIMPORT Storeys& operator=(const Storeys& src);
		MODELLING_EXIMPORT Storey& operator[](int n);
		MODELLING_EXIMPORT const Storey& operator[](int n) const;

	private:
		class Impl;
		Impl* _impl;
	};

	class Building :
		public SpatialElement
	{
	public:
		MODELLING_EXIMPORT Building();
		MODELLING_EXIMPORT Building(const Building& src);
		MODELLING_EXIMPORT ~Building();

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);

		MODELLING_EXIMPORT void initStoreys(int size);
		MODELLING_EXIMPORT int storeySize() const;
		MODELLING_EXIMPORT Storey& storey(int n);
		MODELLING_EXIMPORT const Storey& storey(int n) const;

		MODELLING_EXIMPORT bool modelling(CompoundBody& shapes) const;
		MODELLING_EXIMPORT Polygon2d footprint() const;

		MODELLING_EXIMPORT Building& operator=(const Building& src);

	private:
		Storeys _storeys;
	};

	class Buildings
	{
	public:
		MODELLING_EXIMPORT Buildings();
		MODELLING_EXIMPORT Buildings(const Buildings& src);
		MODELLING_EXIMPORT ~Buildings();

		MODELLING_EXIMPORT void init(int n);
		MODELLING_EXIMPORT void clear();
		MODELLING_EXIMPORT int size() const;

		MODELLING_EXIMPORT Buildings& operator=(const Buildings& src);
		MODELLING_EXIMPORT Building& operator[](int n);
		MODELLING_EXIMPORT const Building& operator[](int n) const;

	private:
		class Impl;
		Impl* _impl;
	};

	class Site :
		public SpatialElement
	{
	public:
		MODELLING_EXIMPORT Site();
		MODELLING_EXIMPORT Site(const Site& src);
		MODELLING_EXIMPORT ~Site();

		MODELLING_EXIMPORT static ObjectType desc();
		MODELLING_EXIMPORT virtual bool isKindOf(ObjectType objType) const;
		MODELLING_EXIMPORT virtual ObjectType type() const;

		MODELLING_EXIMPORT virtual Root* copy() const; // 需要外部释放
		MODELLING_EXIMPORT virtual void copyFrom(const Root* src);

		MODELLING_EXIMPORT void initBuildings(int size);
		MODELLING_EXIMPORT int buildingSize() const;
		MODELLING_EXIMPORT Building& building(int n);
		MODELLING_EXIMPORT const Building& building(int n) const;

		MODELLING_EXIMPORT bool modelling(CompoundBody& shapes) const;
		MODELLING_EXIMPORT Point2d footprintCenter() const;

		MODELLING_EXIMPORT Element* find(const Point& position); // 根据构件的origin查找
		MODELLING_EXIMPORT const Element* find(const Point& position) const; // 根据构件的origin查找

		MODELLING_EXIMPORT Element* find(const TopoDS_Shape& shape);
		MODELLING_EXIMPORT const Element* find(const TopoDS_Shape& shape) const;

		MODELLING_EXIMPORT Site& operator=(const Site& src);

	private:
		Buildings _buildings;
	};

} // namespace meta
