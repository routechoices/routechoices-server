const GeoPdfParser = (() => {
	const isDelimiter = (character) =>
		/\s|[()[\]<>/%]/.test(character);

	function tokenize(source) {
		const tokens = [];
		let index = 0;
		while (index < source.length) {
			const character = source[index];
			if (/\s/.test(character)) {
				index++;
				continue;
			}
			if (character === "%") {
				while (index < source.length && source[index] !== "\n" && source[index] !== "\r") {
					index++;
				}
				continue;
			}
			if (source.startsWith("<<", index) || source.startsWith(">>", index)) {
				tokens.push(source.slice(index, index + 2));
				index += 2;
				continue;
			}
			if (character === "[" || character === "]") {
				tokens.push(character);
				index++;
				continue;
			}
			if (character === "/") {
				const start = ++index;
				while (index < source.length && !isDelimiter(source[index])) {
					index++;
				}
				tokens.push({
					name: source.slice(start, index).replace(/#([0-9a-f]{2})/gi, (_, hex) =>
						String.fromCharCode(Number.parseInt(hex, 16)),
					),
				});
				continue;
			}
			if (character === "(") {
				let depth = 1;
				let value = "";
				index++;
				while (index < source.length && depth > 0) {
					const current = source[index++];
					if (current === "\\") {
						if (index < source.length) {
							value += source[index++];
						}
					} else if (current === "(") {
						depth++;
						value += current;
					} else if (current === ")") {
						depth--;
						if (depth > 0) value += current;
					} else {
						value += current;
					}
				}
				tokens.push({ string: value });
				continue;
			}
			if (character === "<") {
				const end = source.indexOf(">", index + 1);
				if (end === -1) throw new Error("Invalid hex string in PDF.");
				tokens.push({ hex: source.slice(index + 1, end) });
				index = end + 1;
				continue;
			}
			const start = index;
			while (index < source.length && !isDelimiter(source[index])) {
				index++;
			}
			if (start === index) {
				index++;
			} else {
				tokens.push(source.slice(start, index));
			}
		}
		return tokens;
	}

	function parseValue(tokens, state) {
		const token = tokens[state.index++];
		if (token === undefined) throw new Error("Unexpected end of PDF object.");
		if (token === "<<") {
			const dictionary = {};
			while (tokens[state.index] !== ">>") {
				const key = tokens[state.index++];
				if (!key || typeof key !== "object" || !("name" in key)) {
					throw new Error("Invalid PDF dictionary.");
				}
				dictionary[key.name] = parseValue(tokens, state);
			}
			state.index++;
			return dictionary;
		}
		if (token === "[") {
			const values = [];
			while (tokens[state.index] !== "]") {
				values.push(parseValue(tokens, state));
			}
			state.index++;
			return values;
		}
		if (typeof token === "object") {
			if ("name" in token) return token.name;
			if ("string" in token) return token.string;
			return token.hex;
		}
		if (/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(token)) {
			const number = Number(token);
			const next = tokens[state.index];
			const generation = tokens[state.index + 1];
			if (
				Number.isInteger(number) &&
				typeof next === "string" &&
				/^\d+$/.test(next) &&
				generation === "R"
			) {
				state.index += 2;
				return { ref: number };
			}
			return number;
		}
		if (token === "true") return true;
		if (token === "false") return false;
		if (token === "null") return null;
		return token;
	}

	function parseObject(source) {
		return parseValue(tokenize(source), { index: 0 });
	}

	function streamBytes(source, start, end) {
		const streamIndex = source.indexOf("stream", start);
		if (streamIndex === -1 || streamIndex >= end) return null;
		let dataStart = streamIndex + 6;
		if (source[dataStart] === "\r") dataStart++;
		if (source[dataStart] === "\n") dataStart++;
		const dataEnd = source.lastIndexOf("endstream", end);
		if (dataEnd < dataStart) throw new Error("Invalid PDF stream.");
		let trimmedEnd = dataEnd;
		if (source[trimmedEnd - 1] === "\n") trimmedEnd--;
		if (source[trimmedEnd - 1] === "\r") trimmedEnd--;
		const bytes = new Uint8Array(trimmedEnd - dataStart);
		for (let index = 0; index < bytes.length; index++) {
			bytes[index] = source.charCodeAt(dataStart + index) & 0xff;
		}
		return bytes;
	}

	async function decodeStream(bytes, filter) {
		if (!filter) return bytes;
		const filters = Array.isArray(filter) ? filter : [filter];
		let result = bytes;
		for (const currentFilter of filters) {
			if (currentFilter !== "FlateDecode" && currentFilter !== "Fl") {
				throw new Error(`Unsupported GeoPDF stream filter: ${currentFilter}`);
			}
			if (typeof DecompressionStream === "undefined") {
				throw new Error("This browser cannot decompress GeoPDF metadata streams.");
			}
			const stream = new Blob([result]).stream().pipeThrough(new DecompressionStream("deflate"));
			result = new Uint8Array(await new Response(stream).arrayBuffer());
		}
		return result;
	}

	function bytesToString(bytes) {
		const data = bytes instanceof ArrayBuffer ? new Uint8Array(bytes) : bytes;
		let result = "";
		for (let index = 0; index < data.length; index += 0x8000) {
			result += String.fromCharCode(...data.subarray(index, index + 0x8000));
		}
		return result;
	}

	function resolve(value, objects, depth = 0) {
		if (depth > 20) throw new Error("GeoPDF object references are too deeply nested.");
		if (value && typeof value === "object" && !Array.isArray(value) && "ref" in value) {
			if (!objects.has(value.ref)) throw new Error(`Missing PDF object ${value.ref}.`);
			return resolve(objects.get(value.ref), objects, depth + 1);
		}
		if (Array.isArray(value)) {
			return value.map((item) => resolve(item, objects, depth + 1));
		}
		if (value && typeof value === "object") {
			return Object.fromEntries(
				Object.entries(value).map(([key, item]) => [key, resolve(item, objects, depth + 1)]),
			);
		}
		return value;
	}

	function dereference(value, objects) {
		let depth = 0;
		while (value && typeof value === "object" && "ref" in value) {
			if (++depth > 20 || !objects.has(value.ref)) {
				throw new Error("Invalid PDF page-tree reference.");
			}
			value = objects.get(value.ref);
		}
		return value;
	}

	async function parse(buffer) {
		const source = bytesToString(buffer);
		const objects = new Map();
		const objectPattern = /(\d+)\s+\d+\s+obj\b([\s\S]*?)endobj/g;
		for (const match of source.matchAll(objectPattern)) {
			const id = Number(match[1]);
			const bodyStart = match.index + match[0].indexOf(match[2]);
			const streamStart = match[2].indexOf("stream");
			const dictionarySource =
				streamStart === -1 ? match[2] : match[2].slice(0, streamStart);
			const value = parseObject(dictionarySource);
			objects.set(id, value);

			if (value?.Type === "ObjStm") {
				const rawStream = streamBytes(source, bodyStart, match.index + match[0].length);
				if (!rawStream) throw new Error("GeoPDF object stream has no data.");
				const decoded = bytesToString(await decodeStream(rawStream, value.Filter));
				const count = resolve(value.N, objects);
				const first = resolve(value.First, objects);
				const header = decoded.slice(0, first).trim().split(/\s+/).map(Number);
				if (!Number.isInteger(count) || header.length < count * 2) {
					throw new Error("Invalid GeoPDF object stream.");
				}
				for (let index = 0; index < count; index++) {
					const objectId = header[index * 2];
					const offset = header[index * 2 + 1];
					const nextOffset =
						index + 1 < count ? header[(index + 1) * 2 + 1] : decoded.length - first;
					objects.set(objectId, parseObject(decoded.slice(first + offset, first + nextOffset)));
				}
			}
		}

		const catalog = [...objects.values()].find((value) => value?.Type === "Catalog");
		if (!catalog) return null;
		const findFirstPage = (node, depth = 0) => {
			if (depth > 20 || !node) return null;
			const resolvedNode = dereference(node, objects);
			if (resolvedNode.Type === "Page") return resolvedNode;
			for (const child of resolvedNode.Kids || []) {
				const page = findFirstPage(child, depth + 1);
				if (page) return page;
			}
			return null;
		};
		const firstPage = findFirstPage(catalog.Pages);
		if (!firstPage) return null;

		const legacyGeoDictionaries = resolve(firstPage.LGIDict, objects) || [];
		for (const geoDictionary of Array.isArray(legacyGeoDictionaries)
			? legacyGeoDictionaries
			: [legacyGeoDictionaries]) {
			const registration = geoDictionary?.Registration;
			const points = Array.isArray(registration)
				? registration.map((point) => point.map(Number))
				: [];
			if (
				points.length < 4 ||
				points.some(
					(point) =>
						point.length < 4 || point.slice(0, 4).some((coordinate) => !Number.isFinite(coordinate)),
				)
			) {
				continue;
			}
			const xs = points.map(([x]) => x);
			const ys = points.map(([, y]) => y);
			const minX = Math.min(...xs);
			const maxX = Math.max(...xs);
			const minY = Math.min(...ys);
			const maxY = Math.max(...ys);
			const tolerance = Math.max(maxX - minX, maxY - minY) * 1e-8;
			const imageCorners = [
				[minX, maxY],
				[maxX, maxY],
				[maxX, minY],
				[minX, minY],
			];
			const coordinates = imageCorners.map(([x, y]) => {
				const point = points.find(
					([pointX, pointY]) =>
						Math.abs(pointX - x) <= tolerance &&
						Math.abs(pointY - y) <= tolerance,
				);
				return point ? [point[3], point[2]] : null;
			});
			if (coordinates.every(Boolean)) {
				return {
					coordinates,
					wkt: geoDictionary.Projection?.Description || null,
				};
			}
		}

		const viewports = resolve(firstPage.VP, objects);
		for (const viewport of Array.isArray(viewports) ? viewports : [viewports]) {
			const measure = viewport?.Measure;
			const gpts = measure?.GPTS;
			const lpts = measure?.LPTS;
			if (!Array.isArray(gpts) || !Array.isArray(lpts) || gpts.length !== 8 || lpts.length !== 8) {
				continue;
			}
			const localPoints = [];
			for (let index = 0; index < 8; index += 2) {
				localPoints.push([lpts[index], lpts[index + 1]]);
			}
			const imageCorners = [
				[0, 1],
				[1, 1],
				[1, 0],
				[0, 0],
			];
			const coordinates = imageCorners.map((corner) => {
				const pointIndex = localPoints.findIndex(
					(point) =>
						Math.abs(point[0] - corner[0]) < 1e-6 &&
						Math.abs(point[1] - corner[1]) < 1e-6,
				);
				if (pointIndex === -1) return null;
				return [gpts[pointIndex * 2], gpts[pointIndex * 2 + 1]];
			});
			if (coordinates.some((point) => !point || point.some((value) => !Number.isFinite(value)))) {
				continue;
			}
			return {
				coordinates,
				wkt: measure.WKT || null,
			};
		}
		return null;
	}

	return { parse };
})();
