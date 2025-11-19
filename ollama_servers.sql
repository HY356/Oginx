/*
 Ollama Load Balancer - Database Schema

 Source Server Type    : MySQL
 Source Server Version : 5.6.26+
 Target Server Type    : MySQL
 Target Server Version : 5.6.26+
 File Encoding         : 65001

 Description: Ollama服务器配置表结构
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for ollama_servers
-- ----------------------------
DROP TABLE IF EXISTS `ollama_servers`;
CREATE TABLE `ollama_servers`  (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `virtual_model_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '虚拟模型名称',
  `server_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '服务器URL',
  `actual_model_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '实际模型名称',
  `weight` int(11) NULL DEFAULT NULL COMMENT '权重',
  `priority` int(11) NULL DEFAULT NULL COMMENT '优先级(1=primary, 2=fallback)',
  `is_active` tinyint(1) NULL DEFAULT NULL COMMENT '是否启用',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '描述信息',
  `created_at` datetime NULL DEFAULT NULL COMMENT '创建时间',
  `updated_at` datetime NULL DEFAULT NULL COMMENT '更新时间',
  `count` int(11) NULL DEFAULT NULL COMMENT '计数',
  `type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '服务器类型（cpu/gpu）',
  `performance` int(11) NULL DEFAULT NULL COMMENT '所需资源大小',
  `skip_resource_check` tinyint(1) NULL DEFAULT 0 COMMENT '是否跳过资源检测',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 9 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Compact;

SET FOREIGN_KEY_CHECKS = 1;
