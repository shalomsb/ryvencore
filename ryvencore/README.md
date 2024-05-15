# `ryvencore` - overview

## modules

**general**

- `Base.py` includes the base class for all backend (`ryvencore`) components and provides basic functionality like a session-unique integer `ID`, or a placeholder function for frontends to extend serialization processes of specific classes to include frontend data.

**flows**

- `Flow.py` defines flows, see comments in code.
- `Connection.py` defines connections (aka edges) between nodes. There are two types of connections for the two respective types of ports: `data` and `exec`. While usually pure `data` flows are more common and more general, `exec` flows where you have both types of connections (or sometimes also both types but in `data` flows) can make more sense in some cases.
- `FlowExecutor.py` defines custom flow executor classes which provide sophisticated flow execution. These algorithms target specific types of flows to provide more efficient flow execution based on those assumptions and related graph analysis.
- `Node.py` defines nodes, see comments in code.
- `NodePort.py` defines node ports (inputs & outputs), see comments in code.
- `NodePortBP.py` provides simple data containers for `Node.init_inputs, Node.init_outputs` (*BP* for *blueprint*).
- `RC.py` hosts static namespace stuff for this package.
- `Script.py` defines scripts, see comments in code.
- `Session.py` defines sessions, see comments in code. The session is a projects top-level interface and mainly provides functionality to create, change and delete scripts, and save & load projects.

## packages

- `dtypes` defines ryvencore's *dtype* system which lets you define dtypes for data inputs of nodes. Conventionally, a frontend implements specific pre-defined widgets for those dtypes which ensure that all values entered through the widget are serializable. Those dtypes might additionally be extended in the future by clearly defined assert conditions, for example to provide serializability guarantees.
- `logging` provides some simple logging interfaces to enable a nice and simple logging API for nodes, based on python's built-in `logging` module's basic functionality.
- `script_variables` defines ryvencore's script vars system which lets you create, change and delete python variables for scripts and register receiver methods for variable names which receive calls when a variable with the according name changes. Nodes have a simple API for this.
