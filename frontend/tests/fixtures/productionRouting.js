// Local evaluator for the source patterns in the checked-in Vercel contract.
export function rewriteDestination(config, path) {
  for (const rule of config.rewrites) {
    if (rule.source.endsWith('/:path*')) {
      const prefix = rule.source.slice(0, -7);
      if (path === prefix || path.startsWith(prefix + '/')) return rule.destination.replace(':path*', path.slice(prefix.length + 1));
    } else if (rule.source.startsWith('/:path(')) {
      if (new RegExp('^/' + rule.source.slice(7, -1) + '$').test(path)) return rule.destination;
    } else if (path === rule.source) return rule.destination;
  }
  return null;
}
