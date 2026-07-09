'use client';

import React, {
  useRef,
  useEffect,
  useState,
  useMemo,
  useCallback,
} from 'react';

import ForceGraph2D from 'react-force-graph-2d';
import { forceCollide } from 'd3-force';

interface KnowledgeGraphProps {
  memories: any[];
}

interface GraphNode {
  id: string;
  type: 'subject' | 'object';
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  __bckgDimensions?: [number, number];
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  label: string;
  status: string;
}

interface NormalizedMemory {
  subject: string;
  predicate: string;
  object: string;
  epistemicState: string;
}

export default function KnowledgeGraph({
  memories,
}: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);

  /*
   * Prevent repeated automatic fitting.
   *
   * This becomes false only when the actual semantic
   * graph content changes.
   */
  const hasInitialFit = useRef(false);

  /*
   * Keep track of the current graph hash so we can
   * distinguish real graph changes from harmless rerenders.
   */
  const previousGraphHash = useRef('');

  /*
   * Store the fit timeout so it can be cancelled
   * if the component unmounts or graph data changes.
   */
  const fitTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  const [dimensions, setDimensions] = useState({
    width: 0,
    height: 0,
  });

  const [hoverNode, setHoverNode] =
    useState<GraphNode | null>(null);

  /*
   * Normalize memories into only the fields that actually
   * affect the knowledge graph.
   *
   * This prevents unrelated changes elsewhere in a memory
   * object from rebuilding the graph.
   */
  const normalizedMemories = useMemo<NormalizedMemory[]>(() => {
    return memories
      .map((memory) => {
        const subject = memory?.metadata?.subject;
        const object = memory?.metadata?.object;
        const predicate =
          memory?.metadata?.predicate || 'related to';

        if (!subject || !object) {
          return null;
        }

        return {
          subject: String(subject),
          predicate: String(predicate),
          object: String(object),
          epistemicState:
            memory?.metadata?.epistemic_state || 'active',
        };
      })
      .filter(
        (memory): memory is NormalizedMemory =>
          memory !== null
      );
  }, [memories]);

  /*
   * Create a stable content hash.
   *
   * If the backend returns a new array reference containing
   * exactly the same graph information, this hash remains
   * unchanged.
   */
  const graphHash = useMemo(() => {
    return JSON.stringify(normalizedMemories);
  }, [normalizedMemories]);

  /*
   * Build graph data only when the actual semantic
   * content changes.
   */
  const graphData = useMemo(() => {
    const parsedMemories: NormalizedMemory[] =
      JSON.parse(graphHash);

    const nodesMap = new Map<string, GraphNode>();
    const links: GraphLink[] = [];

    parsedMemories.forEach((memory) => {
      const {
        subject,
        object,
        predicate,
        epistemicState,
      } = memory;

      /*
       * Create subject node.
       *
       * If an entity appears as both an object and later
       * a subject, subject takes visual precedence.
       */
      if (!nodesMap.has(subject)) {
        nodesMap.set(subject, {
          id: subject,
          type: 'subject',
        });
      } else {
        const existingNode = nodesMap.get(subject);

        if (existingNode) {
          existingNode.type = 'subject';
        }
      }

      /*
       * Create object node only if it does not already exist.
       */
      if (!nodesMap.has(object)) {
        nodesMap.set(object, {
          id: object,
          type: 'object',
        });
      }

      links.push({
        source: subject,
        target: object,
        label: predicate,
        status: epistemicState,
      });
    });

    return {
      nodes: Array.from(nodesMap.values()),
      links,
    };
  }, [graphHash]);

  /*
   * Track container dimensions.
   *
   * ResizeObserver updates the canvas dimensions without
   * forcing the graph to automatically refit every time.
   */
  useEffect(() => {
    const container = containerRef.current;

    if (!container) return;

    const updateDimensions = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;

      setDimensions((previous) => {
        /*
         * Avoid pointless state updates when dimensions
         * have not actually changed.
         */
        if (
          previous.width === width &&
          previous.height === height
        ) {
          return previous;
        }

        return {
          width,
          height,
        };
      });
    };

    updateDimensions();

    const resizeObserver =
      new ResizeObserver(updateDimensions);

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  /*
   * Reset automatic fitting only when the actual
   * graph content changes.
   *
   * Polling with identical memories will not trigger this.
   */
  useEffect(() => {
    if (previousGraphHash.current === graphHash) {
      return;
    }

    previousGraphHash.current = graphHash;
    hasInitialFit.current = false;

    /*
     * Cancel any pending fit from the previous graph.
     */
    if (fitTimeoutRef.current) {
      clearTimeout(fitTimeoutRef.current);
      fitTimeoutRef.current = null;
    }
  }, [graphHash]);

  /*
   * Configure forces only when the semantic graph changes.
   */
  useEffect(() => {
    if (
      !fgRef.current ||
      graphData.nodes.length === 0
    ) {
      return;
    }

    const graph = fgRef.current;

    /*
     * Moderate repulsion.
     *
     * The old -400 value pushed components too far apart
     * and forced the entire graph to be viewed from orbit.
     */
    graph
      .d3Force('charge')
      ?.strength(-140);

    /*
     * Keep connected nodes relatively close.
     */
    graph
      .d3Force('link')
      ?.distance(75)
      ?.strength(0.8);

    /*
     * Prevent labels and nodes from physically overlapping.
     */
    graph.d3Force(
      'collide',
      forceCollide()
        .radius((node: any) => {
          const labelLength =
            String(node.id).length;

          return Math.min(
            70,
            Math.max(
              32,
              labelLength * 3.5
            )
          );
        })
        .strength(0.9)
        .iterations(2)
    );

    /*
     * Reheat only because the actual graph changed.
     */
    graph.d3ReheatSimulation();
  }, [graphHash, graphData.nodes.length]);

  /*
   * Clean up pending timeout on unmount.
   */
  useEffect(() => {
    return () => {
      if (fitTimeoutRef.current) {
        clearTimeout(fitTimeoutRef.current);
      }
    };
  }, []);

  /*
   * Determine whether a node is directly connected
   * to the currently hovered node.
   */
  const isConnectedToHovered = useCallback(
    (node: GraphNode) => {
      if (!hoverNode) return false;

      if (node.id === hoverNode.id) {
        return true;
      }

      return graphData.links.some((link: any) => {
        const sourceId =
          typeof link.source === 'object'
            ? link.source.id
            : link.source;

        const targetId =
          typeof link.target === 'object'
            ? link.target.id
            : link.target;

        return (
          (
            sourceId === hoverNode.id &&
            targetId === node.id
          ) ||
          (
            targetId === hoverNode.id &&
            sourceId === node.id
          )
        );
      });
    },
    [hoverNode, graphData.links]
  );

  /*
   * Determine whether a link touches the hovered node.
   */
  const isHoveredLink = useCallback(
    (link: any) => {
      if (!hoverNode) return false;

      const sourceId =
        typeof link.source === 'object'
          ? link.source.id
          : link.source;

      const targetId =
        typeof link.target === 'object'
          ? link.target.id
          : link.target;

      return (
        sourceId === hoverNode.id ||
        targetId === hoverNode.id
      );
    },
    [hoverNode]
  );

  /*
   * Empty state.
   */
  if (memories.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-xs italic text-zinc-500">
        The Knowledge Graph is empty. Start a conversation to populate nodes.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="h-full w-full overflow-hidden rounded-xl border border-white/[0.08] bg-[#111111] shadow-inner"
    >
      {dimensions.width > 0 &&
        dimensions.height > 0 && (
          <ForceGraph2D
            ref={fgRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}

            /*
             * Simulation settings.
             */
            d3VelocityDecay={0.3}
            cooldownTicks={120}

            /*
             * Automatically fit only once after a genuine
             * graph-content change.
             *
             * User zoom and pan are preserved afterward.
             */
            onEngineStop={() => {
              if (hasInitialFit.current) {
                return;
              }

              hasInitialFit.current = true;

              if (fitTimeoutRef.current) {
                clearTimeout(
                  fitTimeoutRef.current
                );
              }

              fitTimeoutRef.current =
                setTimeout(() => {
                  fgRef.current?.zoomToFit(
                    500,
                    60
                  );

                  fitTimeoutRef.current =
                    null;
                }, 100);
            }}

            /*
             * Hover behavior.
             *
             * This only changes presentation.
             * It does not touch the simulation or camera.
             */
            onNodeHover={(node: any) => {
              setHoverNode(node || null);

              if (containerRef.current) {
                containerRef.current.style.cursor =
                  node
                    ? 'pointer'
                    : 'grab';
              }
            }}

            /*
             * Link styling.
             */
            linkColor={(link: any) => {
              if (!hoverNode) {
                return 'rgba(255,255,255,0.16)';
              }

              return isHoveredLink(link)
                ? 'rgba(255,255,255,0.65)'
                : 'rgba(255,255,255,0.05)';
            }}

            linkWidth={(link: any) => {
              return isHoveredLink(link)
                ? 2
                : 1.2;
            }}

            /*
             * Slight curvature makes nearby relationships
             * easier to distinguish.
             */
            linkCurvature={0.08}

            /*
             * Relationship particles.
             */
            linkDirectionalParticles={(
              link: any
            ) => {
              return isHoveredLink(link)
                ? 2
                : 1;
            }}

            linkDirectionalParticleWidth={(
              link: any
            ) => {
              return isHoveredLink(link)
                ? 2
                : 1;
            }}

            linkDirectionalParticleSpeed={
              0.004
            }

            linkDirectionalArrowLength={0}

            /*
             * Custom node rendering.
             */
            nodeCanvasObject={(
              node: any,
              ctx,
              globalScale
            ) => {
              const label = String(node.id);

              /*
               * Keep text readable at different zoom levels.
               */
              const screenFontSize =
                globalScale < 0.7
                  ? 10
                  : 12;

              const fontSize =
                screenFontSize /
                globalScale;

              ctx.font = `600 ${fontSize}px Inter, sans-serif`;

              const textWidth =
                ctx.measureText(label).width;

              const horizontalPadding =
                10 / globalScale;

              const verticalPadding =
                7 / globalScale;

              const nodeWidth =
                textWidth +
                horizontalPadding * 2;

              const nodeHeight =
                fontSize +
                verticalPadding * 2;

              const isHovered =
                hoverNode?.id === node.id;

              const isConnected =
                isConnectedToHovered(node);

              /*
               * Fade unrelated nodes while inspecting
               * a local relationship cluster.
               */
              const opacity = hoverNode
                ? isConnected
                  ? 1
                  : 0.22
                : 1;

              ctx.globalAlpha = opacity;

              /*
               * Node shadow.
               */
              if (isHovered) {
                ctx.shadowColor =
                  node.type === 'subject'
                    ? 'rgba(225, 29, 72, 0.75)'
                    : 'rgba(16, 185, 129, 0.75)';

                ctx.shadowBlur =
                  14 / globalScale;

                ctx.shadowOffsetY = 0;
              } else {
                ctx.shadowColor =
                  'rgba(0,0,0,0.45)';

                ctx.shadowBlur =
                  5 / globalScale;

                ctx.shadowOffsetY =
                  2 / globalScale;
              }

              /*
               * Node colors.
               */
              const baseColor =
                node.type === 'subject'
                  ? '#BE123C'
                  : '#059669';

              const hoverColor =
                node.type === 'subject'
                  ? '#E11D48'
                  : '#10B981';

              ctx.fillStyle = isHovered
                ? hoverColor
                : baseColor;

              /*
               * Draw node pill.
               */
              ctx.beginPath();

              if (ctx.roundRect) {
                ctx.roundRect(
                  node.x - nodeWidth / 2,
                  node.y - nodeHeight / 2,
                  nodeWidth,
                  nodeHeight,
                  6 / globalScale
                );
              } else {
                ctx.fillRect(
                  node.x - nodeWidth / 2,
                  node.y - nodeHeight / 2,
                  nodeWidth,
                  nodeHeight
                );
              }

              ctx.fill();

              /*
               * Reset shadow before rendering text.
               */
              ctx.shadowColor =
                'transparent';

              ctx.shadowBlur = 0;
              ctx.shadowOffsetY = 0;

              /*
               * Render node label.
               */
              ctx.fillStyle = '#ffffff';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';

              ctx.fillText(
                label,
                node.x,
                node.y
              );

              ctx.globalAlpha = 1;

              /*
               * Save dimensions for accurate hover detection.
               */
              node.__bckgDimensions = [
                nodeWidth,
                nodeHeight,
              ];
            }}

            /*
             * Accurate pointer interaction area.
             */
            nodePointerAreaPaint={(
              node: any,
              color,
              ctx
            ) => {
              const nodeDimensions =
                node.__bckgDimensions;

              if (!nodeDimensions) {
                return;
              }

              ctx.fillStyle = color;

              ctx.fillRect(
                node.x -
                  nodeDimensions[0] / 2,
                node.y -
                  nodeDimensions[1] / 2,
                nodeDimensions[0],
                nodeDimensions[1]
              );
            }}

            /*
             * Render relationship labels after links.
             */
            linkCanvasObjectMode={() =>
              'after'
            }

            linkCanvasObject={(
              link: any,
              ctx,
              globalScale
            ) => {
              /*
               * Hide predicate labels when zoomed too far out.
               */
              if (globalScale < 0.75) {
                return;
              }

              const start = link.source;
              const end = link.target;

              if (
                typeof start !== 'object' ||
                typeof end !== 'object'
              ) {
                return;
              }

              /*
               * While inspecting a node, hide labels
               * unrelated to that node.
               */
              if (
                hoverNode &&
                !isHoveredLink(link)
              ) {
                return;
              }

              const textPos = {
                x:
                  start.x +
                  (end.x - start.x) / 2,

                y:
                  start.y +
                  (end.y - start.y) / 2,
              };

              const fontSize =
                9 / globalScale;

              ctx.font = `600 ${fontSize}px Inter, sans-serif`;

              const label =
                link.label ||
                'related to';

              const textWidth =
                ctx.measureText(label).width;

              const horizontalPadding =
                5 / globalScale;

              const verticalPadding =
                3 / globalScale;

              const width =
                textWidth +
                horizontalPadding * 2;

              const height =
                fontSize +
                verticalPadding * 2;

              /*
               * Predicate background.
               */
              ctx.fillStyle = '#18181b';

              ctx.beginPath();

              if (ctx.roundRect) {
                ctx.roundRect(
                  textPos.x - width / 2,
                  textPos.y - height / 2,
                  width,
                  height,
                  4 / globalScale
                );
              } else {
                ctx.fillRect(
                  textPos.x - width / 2,
                  textPos.y - height / 2,
                  width,
                  height
                );
              }

              ctx.fill();

              /*
               * Predicate text.
               */
              ctx.fillStyle = '#d4d4d8';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';

              ctx.fillText(
                label,
                textPos.x,
                textPos.y
              );
            }}
          />
        )}
    </div>
  );
}