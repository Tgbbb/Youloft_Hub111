// Midscene ai_prompt 结构化解析/序列化（镜像后端 parse_ai_prompt 的规则）
// 保证前端列表编辑与原文字符串在本包内语义等价，后端仍以 parse_ai_prompt 原样解析执行。

let __seq = 0
function uid() {
  __seq += 1
  return 'ms_' + __seq
}

function clean(text) {
  let repeat = false
  if (text.startsWith('重复')) {
    repeat = true
    text = text.slice(2).trim()
  }
  text = text.replace(/^\d+[.）、]\s*/, '')
  text = text.replace(/^[-*•]\s*/, '')
  return { text, repeat }
}

function newItem(kind, extra) {
  return {
    id: uid(),
    kind,
    text: '',
    repeat: false,
    branchId: null,
    ...(extra || {}),
  }
}

// 文本 -> 顶层步骤数组（branch 会携带 children）
export function parsePrompt(text) {
  const raw = []
  const lines = String(text || '').split('\n')
  for (const line of lines) {
    const stripped = line.trim()
    if (!stripped) continue
    const indent = line.length - line.replace(/^\s+/, '').length
    raw.push({ text: stripped, indent })
  }

  const items = []
  let i = 0
  while (i < raw.length) {
    const { text, indent } = raw[i]
    const { text: instruction, repeat } = clean(text)
    if (!instruction) {
      i += 1
      continue
    }
    const isBranch =
      indent === 0 &&
      (instruction.startsWith('如果') || instruction.startsWith('若')) &&
      /[：:]\s*$/.test(instruction)

    if (isBranch) {
      const children = []
      const elseChildren = []
      let j = i + 1
      let inElse = false
      while (j < raw.length && raw[j].indent > 0) {
        const { text: ct, repeat: crep } = clean(raw[j].text)
        if (ct) {
          if (ct.startsWith('否则') || ct.startsWith('else')) {
            if (inElse) throw new Error(`分支 "${instruction}" 只能有一个否则`)
            inElse = true
          } else if (inElse) {
            elseChildren.push(newItem('child', { text: ct, repeat: crep }))
          } else {
            children.push(newItem('child', { text: ct, repeat: crep }))
          }
        }
        j += 1
      }
      if (children.length === 0 && elseChildren.length === 0) {
        throw new Error(`分支 "${instruction}" 必须至少有一个缩进的子步骤`)
      }
      const prefix = instruction.startsWith('若') ? '若' : '如果'
      let cond = instruction.replace(/[：:]\s*$/, '')
      if (cond.startsWith('如果')) cond = cond.slice(2)
      else if (cond.startsWith('若')) cond = cond.slice(1)
      items.push(newItem('branch', {
        prefix,
        condition: cond.trim(),
        repeat,
        children,
        elseChildren,
      }))
      i = j
    } else {
      items.push(newItem('step', { text: instruction, repeat }))
      i += 1
    }
  }
  return items
}

function prefixOf(item) {
  return item.repeat ? '重复 ' : ''
}

// 顶层步骤数组 -> 规范 ai_prompt 字符串（分支头带 :，子步骤缩进 2 空格）
export function serialize(items) {
  const lines = []
  for (const it of items) {
    if (it.kind === 'branch') {
      lines.push(prefixOf(it) + it.prefix + it.condition + ':')
      for (const c of (it.children || [])) {
        lines.push('  ' + prefixOf(c) + c.text)
      }
      const ec = it.elseChildren || []
      if (ec.length) {
        lines.push(' 否则:')
        for (const c of ec) {
          lines.push('  ' + prefixOf(c) + c.text)
        }
      }
    } else {
      lines.push(prefixOf(it) + it.text)
    }
  }
  return lines.join('\n')
}

// 结构校验：无空步骤、分支必须有非空子步骤、子步骤必须属于其前面的分支
export function validate(items) {
  const errors = []
  const walk = (list) => {
    list.forEach((it) => {
    if (it.kind === 'branch') {
      if (!String(it.condition || '').trim()) errors.push('分支条件不能为空')
      const kids = it.children || []
      if (kids.length === 0 && (it.elseChildren || []).length === 0) {
        errors.push(`分支 "如果${it.condition || ''}:" 必须有至少一个子步骤`)
      } else if (kids.some((k) => !String(k.text || '').trim())) {
        errors.push(`分支 "如果${it.condition || ''}:" 的子步骤不能为空`)
      } else if ((it.elseChildren || []).some((k) => !String(k.text || '').trim())) {
        errors.push(`分支 "如果${it.condition || ''}:" 的否则子步骤不能为空`)
      }
      walk(kids)
      walk(it.elseChildren || [])
    } else if (!String(it.text || '').trim()) {
      errors.push('步骤不能为空')
    }
    })
  }
  walk(items)
  return { ok: errors.length === 0, errors }
}
