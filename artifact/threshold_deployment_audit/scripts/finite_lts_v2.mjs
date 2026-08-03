// Strict finite-LTS schema and exact nonnegative-rational arithmetic.

export const FINITE_LTS_SCHEMA = "finite-acquisition-lts/v2";

const ROOT_REQUIRED = [
  "schema", "initialState", "namedAcquirer", "numeraire",
  "mappedRoutes", "states", "transitions",
];
const ROOT_ALLOWED = new Set([...ROOT_REQUIRED, "description"]);
const NUMERAIRE_REQUIRED = [
  "asset", "unit", "valuationTime", "conversionLowerPrice", "gasTreatment",
];
const TRANSITION_REQUIRED = [
  "id", "from", "to", "route", "success", "usableDelivery",
  "buyerDebit", "debitOrigin", "irreversible", "returnToControl",
  "externalFunding", "buyerPrefund", "prefundOrigin",
];
const TRANSITION_ALLOWED = new Set(TRANSITION_REQUIRED);
const AMOUNT_FIELDS = [
  "buyerDebit", "buyerPrefund", "returnToControl", "externalFunding",
];
const CANONICAL_UINT = /^(0|[1-9][0-9]*)$/;

// JSON.parse silently keeps the last occurrence of a duplicate object member.
// Evidence files must reject that ambiguity before any semantic validation.
export function parseJsonRejectingDuplicateKeys(text, label = "JSON input") {
  if (typeof text !== "string") throw new Error(`${label}: JSON source must be text`);
  let cursor = 0;
  const fail = (message) => { throw new Error(`${label}: ${message} at character ${cursor}`); };
  const whitespace = () => {
    while (cursor < text.length && /[\u0020\u0009\u000a\u000d]/.test(text[cursor])) cursor += 1;
  };
  const stringToken = () => {
    if (text[cursor] !== '"') fail("expected string");
    const start = cursor++;
    while (cursor < text.length) {
      const code = text.charCodeAt(cursor);
      if (text[cursor] === '"') {
        cursor += 1;
        try { return JSON.parse(text.slice(start, cursor)); }
        catch (error) { fail(`invalid string (${error.message})`); }
      }
      if (text[cursor] === "\\") {
        cursor += 1;
        if (cursor >= text.length) fail("unterminated escape");
        if (text[cursor] === "u") {
          const digits = text.slice(cursor + 1, cursor + 5);
          if (!/^[0-9a-fA-F]{4}$/.test(digits)) fail("invalid Unicode escape");
          cursor += 5;
        } else {
          if (!/["\\/bfnrt]/.test(text[cursor])) fail("invalid escape");
          cursor += 1;
        }
      } else {
        if (code < 0x20) fail("unescaped control character in string");
        cursor += 1;
      }
    }
    fail("unterminated string");
  };
  const value = () => {
    whitespace();
    if (cursor >= text.length) fail("expected value");
    if (text[cursor] === "{") return object();
    if (text[cursor] === "[") return array();
    if (text[cursor] === '"') { stringToken(); return; }
    for (const literal of ["true", "false", "null"]) {
      if (text.startsWith(literal, cursor)) { cursor += literal.length; return; }
    }
    const number = text.slice(cursor).match(/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/);
    if (!number) fail("invalid value");
    const token = number[0];
    if (!/^(0|[1-9][0-9]*)$/.test(token) || !Number.isSafeInteger(Number(token))) {
      fail("JSON numbers must be canonical nonnegative safe integers; use a canonical rational string object for other exact amounts");
    }
    cursor += token.length;
  };
  const object = () => {
    cursor += 1;
    whitespace();
    const keys = new Set();
    if (text[cursor] === "}") { cursor += 1; return; }
    while (true) {
      whitespace();
      const key = stringToken();
      if (keys.has(key)) fail(`duplicate object member ${JSON.stringify(key)}`);
      keys.add(key);
      whitespace();
      if (text[cursor] !== ":") fail("expected colon after object member");
      cursor += 1;
      value();
      whitespace();
      if (text[cursor] === "}") { cursor += 1; return; }
      if (text[cursor] !== ",") fail("expected comma or closing brace");
      cursor += 1;
    }
  };
  const array = () => {
    cursor += 1;
    whitespace();
    if (text[cursor] === "]") { cursor += 1; return; }
    while (true) {
      value();
      whitespace();
      if (text[cursor] === "]") { cursor += 1; return; }
      if (text[cursor] !== ",") fail("expected comma or closing bracket");
      cursor += 1;
    }
  };
  whitespace();
  value();
  whitespace();
  if (cursor !== text.length) fail("trailing content");
  try { return JSON.parse(text); }
  catch (error) { throw new Error(`${label}: invalid JSON: ${error.message}`); }
}

const isPlainObject = (value) => value !== null
  && typeof value === "object"
  && !Array.isArray(value)
  && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);

function gcd(a, b) {
  let x = a < 0n ? -a : a;
  let y = b < 0n ? -b : b;
  while (y !== 0n) [x, y] = [y, x % y];
  return x;
}

function rat(numerator, denominator = 1n) {
  if (denominator <= 0n || numerator < 0n) throw new Error("rational must be nonnegative with positive denominator");
  const divisor = gcd(numerator, denominator);
  return Object.freeze({ n: numerator / divisor, d: denominator / divisor });
}

export const ZERO = rat(0n);

export function parseExactAmount(value, label = "amount") {
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new Error(`${label} must be a nonnegative safe integer or canonical rational object`);
    }
    return rat(BigInt(value));
  }
  if (!isPlainObject(value)) {
    throw new Error(`${label} must be a nonnegative safe integer or canonical rational object`);
  }
  const keys = Object.keys(value).sort();
  if (keys.length !== 2 || keys[0] !== "denominator" || keys[1] !== "numerator") {
    throw new Error(`${label} rational object must contain exactly numerator and denominator`);
  }
  if (typeof value.numerator !== "string" || !CANONICAL_UINT.test(value.numerator)) {
    throw new Error(`${label}.numerator must be a canonical unsigned decimal string`);
  }
  if (typeof value.denominator !== "string" || !CANONICAL_UINT.test(value.denominator) || value.denominator === "0") {
    throw new Error(`${label}.denominator must be a canonical positive decimal string`);
  }
  const numerator = BigInt(value.numerator);
  const denominator = BigInt(value.denominator);
  if (gcd(numerator, denominator) !== 1n) {
    throw new Error(`${label} rational object must be reduced`);
  }
  return rat(numerator, denominator);
}

export const addAmount = (a, b) => rat(a.n * b.d + b.n * a.d, a.d * b.d);
export const subtractAmount = (a, b) => {
  const numerator = a.n * b.d - b.n * a.d;
  if (numerator < 0n) throw new Error("exact amount subtraction would be negative");
  return rat(numerator, a.d * b.d);
};
export const compareAmount = (a, b) => {
  const delta = a.n * b.d - b.n * a.d;
  return delta < 0n ? -1 : delta > 0n ? 1 : 0;
};
export const isZeroAmount = (value) => value.n === 0n;
export const isPositiveAmount = (value) => value.n > 0n;
export const minAmount = (a, b) => compareAmount(a, b) <= 0 ? a : b;
export const amountToString = (value) => value.d === 1n ? value.n.toString() : `${value.n}/${value.d}`;
export function amountToJson(value) {
  if (value.d === 1n && value.n <= BigInt(Number.MAX_SAFE_INTEGER)) return Number(value.n);
  return { numerator: value.n.toString(), denominator: value.d.toString() };
}

function exactKeys(value, allowed, label, errors) {
  if (!isPlainObject(value)) {
    errors.push(`${label} must be an object`);
    return;
  }
  for (const key of Object.keys(value)) if (!allowed.has(key)) errors.push(`${label} has unknown field ${key}`);
}

function nonemptyString(value) {
  return typeof value === "string" && value.length > 0;
}

export function validateFiniteLts(lts) {
  const errors = [];
  const amounts = new Map();
  if (!isPlainObject(lts)) return { ok: false, errors: ["finite LTS must be an object"], amounts };
  exactKeys(lts, ROOT_ALLOWED, "finite LTS", errors);
  for (const field of ROOT_REQUIRED) if (!own(lts, field)) errors.push(`finite LTS missing ${field}`);
  if (lts.schema !== FINITE_LTS_SCHEMA) errors.push(`schema must be ${FINITE_LTS_SCHEMA}`);
  if (!nonemptyString(lts.initialState)) errors.push("initialState must be a nonempty string");
  if (!nonemptyString(lts.namedAcquirer) || lts.namedAcquirer === "none") errors.push("namedAcquirer must be a nonempty principal other than none");

  if (!isPlainObject(lts.numeraire)) errors.push("numeraire must be an object");
  else {
    exactKeys(lts.numeraire, new Set(NUMERAIRE_REQUIRED), "numeraire", errors);
    for (const field of NUMERAIRE_REQUIRED) {
      if (!own(lts.numeraire, field)) errors.push(`numeraire missing ${field}`);
      else if (!nonemptyString(lts.numeraire[field])) errors.push(`numeraire.${field} must be a nonempty string`);
    }
  }

  const states = Array.isArray(lts.states) ? lts.states : [];
  if (!Array.isArray(lts.states) || states.length === 0) errors.push("states must be a nonempty array");
  states.forEach((state, index) => { if (!nonemptyString(state)) errors.push(`states[${index}] must be a nonempty string`); });
  if (new Set(states).size !== states.length) errors.push("states must be unique");
  const stateSet = new Set(states);
  if (nonemptyString(lts.initialState) && !stateSet.has(lts.initialState)) errors.push("initialState is not in states");

  const mappedRoutes = Array.isArray(lts.mappedRoutes) ? lts.mappedRoutes : [];
  if (!Array.isArray(lts.mappedRoutes)) errors.push("mappedRoutes must be an array");
  mappedRoutes.forEach((route, index) => { if (!nonemptyString(route)) errors.push(`mappedRoutes[${index}] must be a nonempty string`); });
  if (new Set(mappedRoutes).size !== mappedRoutes.length) errors.push("mappedRoutes must be unique");

  const transitions = Array.isArray(lts.transitions) ? lts.transitions : [];
  if (!Array.isArray(lts.transitions) || transitions.length === 0) errors.push("transitions must be a nonempty array");
  const ids = [];
  const usedRoutes = new Set();
  transitions.forEach((transition, index) => {
    const label = `transitions[${index}]`;
    if (!isPlainObject(transition)) {
      errors.push(`${label} must be an object`);
      return;
    }
    exactKeys(transition, TRANSITION_ALLOWED, label, errors);
    for (const field of TRANSITION_REQUIRED) if (!own(transition, field)) errors.push(`${label} missing ${field}`);
    for (const field of ["id", "from", "to", "route", "debitOrigin", "prefundOrigin"]) {
      if (own(transition, field) && !nonemptyString(transition[field])) errors.push(`${label}.${field} must be a nonempty string`);
    }
    if (nonemptyString(transition.id)) ids.push(transition.id);
    if (nonemptyString(transition.route)) usedRoutes.add(transition.route);
    if (nonemptyString(transition.from) && !stateSet.has(transition.from)) errors.push(`${label}.from is not in states`);
    if (nonemptyString(transition.to) && !stateSet.has(transition.to)) errors.push(`${label}.to is not in states`);
    for (const field of ["success", "usableDelivery", "irreversible"]) {
      if (own(transition, field) && typeof transition[field] !== "boolean") errors.push(`${label}.${field} must be boolean`);
    }
    const parsed = {};
    for (const field of AMOUNT_FIELDS) {
      if (!own(transition, field)) continue;
      try { parsed[field] = parseExactAmount(transition[field], `${label}.${field}`); }
      catch (error) { errors.push(error.message); }
    }
    amounts.set(transition, parsed);
    if (parsed.buyerDebit && nonemptyString(transition.debitOrigin)) {
      if (isZeroAmount(parsed.buyerDebit) !== (transition.debitOrigin === "none")) {
        errors.push(`${label} has conflicting buyerDebit and debitOrigin`);
      }
    }
    if (parsed.buyerPrefund && nonemptyString(transition.prefundOrigin)) {
      if (isZeroAmount(parsed.buyerPrefund) !== (transition.prefundOrigin === "none")) {
        errors.push(`${label} has conflicting buyerPrefund and prefundOrigin`);
      }
    }
  });
  if (new Set(ids).size !== ids.length) errors.push("transition ids must be unique");
  for (const route of mappedRoutes) if (!usedRoutes.has(route)) errors.push(`mapped route ${route} has no transition`);
  return { ok: errors.length === 0, errors, amounts };
}

export function requireFiniteLts(lts) {
  const validation = validateFiniteLts(lts);
  if (!validation.ok) throw new Error(`malformed finite LTS: ${validation.errors.join("; ")}`);
  return validation;
}
