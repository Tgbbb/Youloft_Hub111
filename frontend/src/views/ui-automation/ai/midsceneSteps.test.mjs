import { strict as assert } from 'node:assert'
import { parsePrompt, serialize, validate } from './midsceneSteps.mjs'

// 1. 分支组解析
const items = parsePrompt('打开应用\n如果展示会员购买页:\n    点击左上角关闭\n    点击下次一定\n输入密码')
assert.equal(items.length, 3, '应为 3 个顶层项')
assert.equal(items[1].kind, 'branch')
assert.equal(items[1].condition, '展示会员购买页')
assert.equal(items[1].children.length, 2)

// 2. 单条件不带冒号 -> 普通步骤，不是分支
const flat = parsePrompt('如果展示会员购买页，就点击左上角关闭\n点击返回')
assert.equal(flat[0].kind, 'step')
assert.equal(flat[0].text, '如果展示会员购买页，就点击左上角关闭')

// 3. 缩进子步骤不会被当成嵌套分支
const nested = parsePrompt('如果A:\n    如果B:\n    点击C')
assert.equal(nested[0].kind, 'branch')
assert.equal(nested[0].children.length, 2) // 如果B: 与 点击C 都是普通子步骤
assert.equal(nested[0].children[0].text, '如果B:')

// 4. 重复前缀保留
const rep = parsePrompt('重复 点击登录')
assert.equal(rep[0].repeat, true)
assert.equal(rep[0].text, '点击登录')
assert.equal(serialize(rep), '重复 点击登录')

// 5. 无子步骤分支报错
assert.throws(() => parsePrompt('如果展示会员页:'))

// 6. 往返稳定：parse(serialize(parse(text))) 结构与 parse(text) 等价
for (const text of [
  '打开应用\n如果展示会员页:\n    点击左上角关闭\n    点击下次一定\n输入密码',
  '如果展示会员页，就点击左上角关闭\n点击返回',
  '重复 点击登录',
  '点击获取验证码\n输入111111\n如果进入引导页:\n    点击知道了\n    关闭弹窗',
]) {
  const once = parsePrompt(text)
  const twice = parsePrompt(serialize(once))
  assert.deepEqual(serialize(twice), serialize(once), '往返不稳定: ' + text)
}

// 7. 校验
assert.equal(validate(parsePrompt('点击登录\n如果A:\n  点击B')).ok, true)
assert.throws(() => parsePrompt('如果A:'))
assert.equal(validate([{ kind: 'branch', prefix: '如果', condition: 'A', children: [] }]).ok, false)
const emptyInv = parsePrompt('点击登录')
emptyInv[0].text = ''
assert.equal(validate(emptyInv).ok, false)

// 8. 后端一致性的规范化输出样例
console.log(JSON.stringify({
  branch: serialize(parsePrompt('打开应用\n如果展示会员页:\n    点击左上角关闭\n    点击下次一定\n输入密码')),
  single: serialize(parsePrompt('如果展示会员页，就点击左上角关闭\n点击返回')),
  repeat: serialize(parsePrompt('重复 点击登录')),
}, null, 2))

// 8. else 分支解析/序列化
const elseItems = parsePrompt('如果展示会员页:\n  点击左上角关闭\n  否则:\n  点击跳过')
assert.equal(elseItems[0].kind, 'branch')
assert.equal(elseItems[0].children.length, 1)
assert.equal(elseItems[0].elseChildren.length, 1)
assert.equal(elseItems[0].elseChildren[0].text, '点击跳过')
const elseSerialized = serialize(elseItems)
assert.match(elseSerialized, /否则:/)
assert.equal(parsePrompt(elseSerialized)[0].children.length, 1)
assert.equal(parsePrompt(elseSerialized)[0].elseChildren.length, 1)

// 9. 往返稳定（含 else）
for (const text of [
  '如果展示会员页:\n  点击左上角关闭\n  否则:\n  点击跳过\n  点击返回',
  '如果A:\n  点击B\n  否则:\n  点击C',
]) {
  const once = parsePrompt(text)
  const twice = parsePrompt(serialize(once))
  assert.deepEqual(serialize(twice), serialize(once), 'else 往返不稳定: ' + text)
}

// 10. 有 else 子步骤即合法
const noKids = parsePrompt('如果A:\n  否则:\n  点击B')
assert.equal(validate(noKids).ok, true)
console.log('all midsceneSteps tests pass')
