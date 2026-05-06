/*
Navicat MySQL Data Transfer

Source Server         : 腾讯云
Source Server Version : 50744
Source Host           : 49.232.128.132:3306
Source Database       : lovestory

Target Server Type    : MYSQL
Target Server Version : 50744
File Encoding         : 65001

Date: 2026-05-06 15:03:43
*/

SET FOREIGN_KEY_CHECKS=0;

-- ----------------------------
-- Table structure for `photo`
-- ----------------------------
DROP TABLE IF EXISTS `photo`;
CREATE TABLE `photo` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `path` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '照片在OSS上的存储路径',
  `type` enum('cat','girl','us') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '照片类型：cat-猫, girl-女孩, us-我们',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `description` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_type` (`type`) COMMENT '类型索引'
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='照片信息表';

-- ----------------------------
-- Records of photo
-- ----------------------------
INSERT INTO `photo` VALUES ('7', 'love530/lovestory/photos/cat/2026/04/28/1566a9d9-405e-4153-9267-b83e30b74b3a.jpg', 'cat', '2026-04-28 23:21:35', '2026-04-28 23:21:35', null);
INSERT INTO `photo` VALUES ('8', 'love530/lovestory/photos/us/2026/04/30/e575767f-70d2-46bf-a296-45c7d5ad5981.jpg', 'us', '2026-04-30 17:00:43', '2026-04-30 17:00:43', null);
INSERT INTO `photo` VALUES ('9', 'love530/lovestory/photos/girl/2026/05/04/8869e02e-43cc-4533-a594-7f31b4c1fb9d.jpg', 'girl', '2026-05-04 21:25:30', '2026-05-04 21:25:30', null);
INSERT INTO `photo` VALUES ('10', 'love530/lovestory/photos/us/2026/05/06/17b7277d-f7c0-45b8-a55b-fa91a32856fb.jpeg', 'us', '2026-05-06 11:28:29', '2026-05-06 11:28:29', null);
INSERT INTO `photo` VALUES ('11', 'love530/lovestory/photos/cat/2026/05/06/2be193b8-cd0c-4197-ab8d-d4a3f7746942.jpeg', 'cat', '2026-05-06 11:28:59', '2026-05-06 11:28:59', null);
INSERT INTO `photo` VALUES ('12', 'love530/lovestory/photos/us/2026/05/06/80fe3f35-2dff-470c-a466-07400fe316d5.jpeg', 'us', '2026-05-06 11:29:39', '2026-05-06 11:29:39', null);
INSERT INTO `photo` VALUES ('13', 'love530/lovestory/photos/us/2026/05/06/9f0fdfc6-0ab4-473d-8dd5-da5d9e379dd7.jpeg', 'us', '2026-05-06 11:30:20', '2026-05-06 11:30:20', null);
INSERT INTO `photo` VALUES ('14', 'love530/lovestory/photos/cat/2026/05/06/0679b9f3-d6b3-4b58-a5f5-091c235bc9da.jpeg', 'cat', '2026-05-06 11:30:57', '2026-05-06 11:30:57', null);
INSERT INTO `photo` VALUES ('15', 'love530/lovestory/photos/us/2026/05/06/4800cc7a-fd6d-432e-9553-4011afb4cdc7.jpeg', 'us', '2026-05-06 11:31:52', '2026-05-06 11:31:52', null);
