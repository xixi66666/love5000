import test from 'node:test';
import assert from 'node:assert/strict';
import { validatePhone, validatePassword, validateNickname } from '../../main/resources/static/js/auth.js';

test('手机号边界与格式校验', () => {
  assert.equal(validatePhone('13800138000'), '');
  assert.notEqual(validatePhone('1380013800'), '');
  assert.notEqual(validatePhone('12800138000'), '');
  assert.equal(validatePhone(' 13800138000 '), '');
});

test('密码必须满足长度、字母、数字且不含空白', () => {
  assert.equal(validatePassword('guitar123'), '');
  assert.notEqual(validatePassword('short1'), '');
  assert.notEqual(validatePassword('guitarpassword'), '');
  assert.notEqual(validatePassword('guitar 123'), '');
  assert.notEqual(validatePassword('a'.repeat(73) + '1'), '');
});

test('昵称去除空白后限制 1 到 30 个字符', () => {
  assert.equal(validateNickname('  木吉他  '), '');
  assert.notEqual(validateNickname('   '), '');
  assert.notEqual(validateNickname('a'.repeat(31)), '');
});
