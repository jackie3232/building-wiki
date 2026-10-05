## 院落 (courtyard)

结构.desc：基本空间单元：由房屋围合出的露天院落
结构.center.ref：tingyuan
结构.center.desc：院落中心（露天）
结构.gate.ref：chuihuamen
结构.gate.desc：院落边界上的门本体——不挂在任何建筑上（如卡子墙正中的垂花门）。设在何处分界、何时设，由 rules.occupancy / rules.position 声明，本图谱不重复。
结构.peripheral[0].ref：youlang
结构.peripheral[0].desc：游廊连接各屋（可选）。【当前不启用】几何层各进 peripheral 未声明 youlang，留待加细节阶段确定抄手游廊形制与归属后再恢复
结构.peripheral[1].ref：yingbi
结构.peripheral[1].desc：门内影壁（可选）：正对宅门、立于门内侧，归宅门所在之院（第一进）
结构.peripheral[2].ref：erfang
结构.peripheral[2].attachToRef：zhengfang
结构.peripheral[2].cond：optional
结构.peripheral[2].desc：耳房接正房两侧（可选）。⚠️ 本条 cond 属越界（「可选」应归 rules），但 rules 侧目前无等价声明，暂留此处以免该事实失源；待迁入 rules.occupancy 后删除 cond。
结构.peripheral[3].ref：houzhaofang
结构.peripheral[3].desc：后罩房位于正房之后。出现条件（末进 + jin>=3）由 rules.occupancy 声明，本图谱不重复。
结构.ring.ref：weihe
结构.ring.desc：院落连续围墙基底（boundarySegmentRealization 院墙环分段实现）：每院先有一道完整四侧墙环（纯围墙基线）；叠加建筑后，其贴边界的后檐墙分段实现（替换）对应围墙段；建筑间空隙由补墙/游廊填。每侧墙基底恒在——该侧有建筑则由其后檐墙分段实现，无建筑则为独立院墙（缺省由谁实现，归 rules.occupancy）。
结构.ring.sides.bei.wallRef：yuanqiang
结构.ring.sides.bei.desc：北墙基底
结构.ring.sides.nan.wallRef：yuanqiang
结构.ring.sides.nan.desc：南墙基底
结构.ring.sides.dong.wallRef：yuanqiang
结构.ring.sides.dong.desc：东墙基底
结构.ring.sides.xi.wallRef：yuanqiang
结构.ring.sides.xi.desc：西墙基底
