"""Pure-python algorithms: Dijkstra (+shortest-path tree), Prim MST (tree),
greedy nearest-neighbour TSP, MST 2-approx TSP, 2-opt improvement."""
import heapq, math


def haversine(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def dijkstra(adj, src):
    """adj: {u: [(v, w), ...]}. Returns (dist, parent). parent forms the shortest-path TREE.
    O((V+E) log V) with a binary heap."""
    dist = {src: 0.0}
    parent = {src: None}
    pq = [(0.0, src)]
    done = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u)
        for v, w in adj.get(u, ()):
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                parent[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, parent


def path_from_tree(parent, dst):
    if dst not in parent:
        return []
    p = []
    while dst is not None:
        p.append(dst)
        dst = parent[dst]
    return p[::-1]


def knn_graph(matrix, k=4):
    """Sparse graph: each node linked to its k nearest (symmetrised). Keeps Dijkstra meaningful."""
    n = len(matrix)
    adj = {i: {} for i in range(n)}
    for i in range(n):
        near = sorted((j for j in range(n) if j != i), key=lambda j: matrix[i][j])[:k]
        for j in near:
            adj[i][j] = matrix[i][j]
            adj[j][i] = matrix[j][i]
    return {i: list(nb.items()) for i, nb in adj.items()}


def prim_mst(matrix):
    """Returns tree as {u: [children]} rooted at 0. O(n^2)."""
    n = len(matrix)
    inT = [False] * n
    key = [math.inf] * n
    par = [-1] * n
    key[0] = 0
    for _ in range(n):
        u = min((i for i in range(n) if not inT[i]), key=lambda i: key[i])
        inT[u] = True
        for v in range(n):
            if not inT[v] and matrix[u][v] < key[v]:
                key[v] = matrix[u][v]
                par[v] = u
    tree = {i: [] for i in range(n)}
    for v in range(1, n):
        tree[par[v]].append(v)
    return tree


def preorder(tree, root=0):
    out, st = [], [root]
    while st:
        u = st.pop()
        out.append(u)
        st.extend(reversed(tree[u]))
    return out


def tour_len(order, m):
    return sum(m[order[i]][order[i + 1]] for i in range(len(order) - 1))


def greedy_nn(matrix, start=0, end=None):
    """Greedy nearest-neighbour. If end is given, it is forced to be last. O(n^2)."""
    n = len(matrix)
    left = set(range(n)) - {start} - ({end} if end is not None else set())
    order, cur = [start], start
    while left:
        cur = min(left, key=lambda j: matrix[cur][j])
        left.remove(cur)
        order.append(cur)
    if end is not None:
        order.append(end)
    return order


def mst_tsp(matrix, start=0, end=None):
    """MST preorder walk (2-approx for metric TSP); rotated to honour start/end if possible."""
    order = preorder(prim_mst(matrix), 0)
    if start != 0:
        i = order.index(start)
        order = order[i:] + order[:i]
    if end is not None:
        order.remove(end)
        order.append(end)
    return order


def two_opt(order, matrix, fixed_ends=True):
    """Local-search improvement of an open path."""
    best = order[:]
    improved = True
    lo = 1 if fixed_ends else 0
    hi = len(best) - 1 if fixed_ends else len(best)
    while improved:
        improved = False
        for i in range(lo, hi - 1):
            for j in range(i + 1, hi):
                a, b = best[i - 1], best[i]
                c = best[j]
                d = best[j + 1] if j + 1 < len(best) else None
                old = matrix[a][b] + (matrix[c][d] if d is not None else 0)
                new = matrix[a][c] + (matrix[b][d] if d is not None else 0)
                if new < old - 1e-9:
                    best[i:j + 1] = reversed(best[i:j + 1])
                    improved = True
    return best
