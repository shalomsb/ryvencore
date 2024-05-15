from .Base import Base, Event
from .Connection import Connection, DataConnection, ExecConnection
from .FlowExecutor import DataFlowOptimized, FlowExecutor
from .Node import Node
from .NodePort import NodePort
from .RC import FlowAlg, PortObjPos
from .utils import node_from_identifier
from typing import List, Dict, Optional


class Flow(Base):
    """
    Manages all abstract flow components (nodes, connections) and includes implementations for editing.
    """

    def __init__(self, session, script):
        Base.__init__(self)

        # events
        self.node_added = Event(Node)
        self.node_removed = Event(Node)
        self.connection_added = Event(Connection)
        self.connection_removed = Event(Connection)

        self.connection_request_valid = Event(bool)
        self.nodes_created_from_data = Event(list)
        self.connections_created_from_data = Event(list)

        self.algorithm_mode_changed = Event(str)

        # general attributes
        self.session = session
        self.script = script
        self.nodes: [Node] = []
        self.connections: [Connection] = []

        self.alg_mode = FlowAlg.DATA

        # special executors
        self.executor_data_opt = DataFlowOptimized(self)
        self.executor: FlowExecutor = None
        self.running_with_executor = False
        self._update_running_with_executor()
        #   additional data structures for executors
        self.node_successors = {}


    def load(self, data):
        """Loading a flow from data"""

        # algorithm mode
        mode = data['algorithm mode']
        if mode == 'data' or mode == 'data flow':
            self.set_algorithm_mode('data')
        elif mode == 'data opt':
            self.set_algorithm_mode('data opt')
        elif mode == 'exec' or mode == 'exec flow':
            self.set_algorithm_mode('exec')

        # build flow

        new_nodes = self.create_nodes_from_data(data['nodes'])

        #   the following connections should not cause updates in sequential nodes
        blocked_nodes = filter(lambda n: n.block_init_updates, new_nodes)
        for node in blocked_nodes:
            node.block_updates = True

        self.connect_nodes_from_data(new_nodes, data['connections'])

        for node in blocked_nodes:
            node.block_updates = False


    def create_nodes_from_data(self, nodes_data: List):
        """Creates Nodes from nodes_data, previously returned by data()"""

        nodes = []

        for n_c in nodes_data:

            # find class
            node_class = node_from_identifier(
                n_c['identifier'],
                self.session.nodes + self.session.invisible_nodes
            )

            node = self.create_node(node_class, n_c)
            nodes.append(node)

        self.nodes_created_from_data.emit(nodes)

        return nodes


    def create_node(self, node_class, data=None):
        """Creates, adds and returns a new node object"""

        node = node_class((self, self.session, data))
        # node.finish_initialization()
        # node.load_user_data()  # --> Node.set_state()
        node.initialize()
        self.add_node(node)
        return node


    def add_node(self, node: Node):
        """Stores a node object and causes the node's place_event()"""

        self.nodes.append(node)
        self.node_successors[node] = []
        node.after_placement()
        self.flow_changed()

        # self.emit_event('node added', (node,))    # ALPHA
        self.node_added.emit(node)


    def node_view_placed(self, node: Node):
        """Triggered after the node's GUI content has been fully initialized"""

        node.view_place_event()


    def remove_node(self, node: Node):
        """Removes a node from internal list without deleting it"""

        node.prepare_removal()
        self.nodes.remove(node)
        # del self.node_successors[node]
        self.flow_changed()

        # self.emit_event('node removed', (node,))    # ALPHA
        self.node_removed.emit(node)


    def connect_nodes_from_data(self, nodes: List[Node], data: List):
        connections = []

        for c in data:

            c_parent_node_index = c['parent node index']
            c_connected_node_index = c['connected node']
            c_output_port_index = c['output port index']
            c_connected_input_port_index = c['connected input port index']

            if c_connected_node_index is not None:  # which can be the case when pasting
                parent_node = nodes[c_parent_node_index]
                connected_node = nodes[c_connected_node_index]

                c = self.connect_nodes(parent_node.outputs[c_output_port_index],
                                       connected_node.inputs[c_connected_input_port_index])
                connections.append(c)

        self.connections_created_from_data.emit(connections)

        return connections


    def check_connection_validity(self, p1: NodePort, p2: NodePort) -> bool:
        """Checks whether a considered connect action is legal"""

        valid = True

        if p1.node == p2.node:
            valid = False

        if p1.io_pos == p2.io_pos or p1.type_ != p2.type_:
            valid = False

        self.connection_request_valid.emit(valid)

        return valid


    def connect_nodes(self, p1: NodePort, p2: NodePort) -> Connection:
        """Connects nodes or disconnects them if they are already connected"""

        if not self.check_connection_validity(p1, p2):
            return None

        out = p1
        inp = p2
        if out.io_pos == PortObjPos.INPUT:
            out, inp = inp, out

        for c in out.connections:
            if c.inp == inp:
                # DISCONNECT
                self.remove_connection(c)
                return None

        # c = self.session.CLASSES['data conn']((out, inp, self)) if out.type_ == 'data' else \
        #     self.session.CLASSES['exec conn']((out, inp, self))
        c = DataConnection((out, inp, self)) if out.type_ == 'data' else \
            ExecConnection((out, inp, self))

        self.add_connection(c)

        return c


    def add_connection(self, c: Connection):
        """Adds a connection object"""

        c.out.connections.append(c)
        c.inp.connections.append(c)
        c.out.connected()
        c.inp.connected()
        self.connections.append(c)

        self.node_successors[c.out.node].append(c.inp.node)
        self.flow_changed()

        # self.emit_event('connection added', (c,))    # ALPHA
        self.connection_added.emit(c)


    def remove_connection(self, c: Connection):
        """Removes a connection object without deleting it"""

        c.out.connections.remove(c)
        c.inp.connections.remove(c)
        c.out.disconnected()
        c.inp.disconnected()
        self.connections.remove(c)

        self.node_successors[c.out.node].remove(c.inp.node)
        self.flow_changed()

        # self.emit_event('connection removed', (c,))    # ALPHA
        self.connection_removed.emit(c)


    def algorithm_mode(self) -> str:
        """Returns the current algorithm mode of the flow as string"""

        return FlowAlg.str(self.alg_mode)


    def set_algorithm_mode(self, mode: str):
        """Sets the algorithm mode of the flow, possible values are 'data' and 'exec'"""

        new_alg_mode = FlowAlg.from_str(mode)
        if new_alg_mode is None:
            return False

        self.alg_mode = new_alg_mode
        self._update_running_with_executor()
        self.algorithm_mode_changed.emit(self.algorithm_mode())

        return True


    def _update_running_with_executor(self):
        self.running_with_executor = self.alg_mode in (FlowAlg.DATA_OPT, )

        if self.running_with_executor:
            if self.alg_mode == FlowAlg.DATA_OPT:
                self.executor = self.executor_data_opt
        else:
            self.executor = None


    def flow_changed(self):
        self.executor_data_opt.flow_changed = True


    def data(self) -> dict:
        return {
            'algorithm mode': FlowAlg.str(self.alg_mode),
            'nodes': self.gen_nodes_data(self.nodes),
            'connections': self.gen_conns_data(self.nodes),
            'GID': self.GLOBAL_ID,
        }


    def gen_nodes_data(self, nodes: List[Node]) -> List[dict]:
        """Returns the data dicts of the nodes given"""

        return [n.data() for n in nodes]


    def gen_conns_data(self, nodes: List[Node]) -> List[dict]:
        """Generates the connections data between and relative to the nodes passed"""

        # notice that this is intentionally not part of Connection, because connection data
        # is generated always for a specific set of nodes (like all currently selected ones)
        # and the data dict therefore has the refer to the indices of the nodes in the nodes list

        data = []
        for i in range(len(nodes)):
            n = nodes[i]
            for j in range(len(n.outputs)):
                out = n.outputs[j]
                for c in out.connections:
                    connected_port = c.inp
                    connected_node = connected_port.node

                    # ignore connections connecting to nodes not in the list
                    if connected_node not in nodes:
                        continue

                    data.append({
                        'GID': c.GLOBAL_ID,
                        'parent node index': i,
                        'output port index': j,
                        'connected node': nodes.index(connected_node),
                        'connected input port index': connected_node.inputs.index(connected_port)
                    })

        return data
